"""CBC first (pulp==2.9.0). Native HiGHS if the bundled CBC binary is the wrong arch."""

from __future__ import annotations

import shutil

import numpy as np
import pulp


def solve_mip(problem: pulp.LpProblem, time_limit_s: int = 10, mip_gap: float = 0.01, threads: int = 2, msg: int = 0) -> int:
    """Return a pulp status code and fill variable values."""
    native = shutil.which("cbc")
    if native:
        return problem.solve(
            pulp.COIN_CMD(path=native, msg=msg, timeLimit=time_limit_s, gapRel=mip_gap, threads=threads)
        )
    try:
        return problem.solve(
            pulp.PULP_CBC_CMD(msg=msg, timeLimit=time_limit_s, gapRel=mip_gap, threads=threads)
        )
    except OSError:
        return _solve_highs(problem, time_limit_s, mip_gap, threads)


def _solve_highs(problem: pulp.LpProblem, time_limit_s: int, mip_gap: float, threads: int) -> int:
    try:
        import highspy
    except Exception as exc:
        raise RuntimeError(
            "CBC is unavailable on this CPU (pulp 2.9 ships an x86_64 macOS binary) "
            "and highspy is not installed. pip install highspy"
        ) from exc

    variables = list(problem.variables())
    n = len(variables)
    index = {id(v): i for i, v in enumerate(variables)}
    inf = float(highspy.kHighsInf)

    col_lo = np.zeros(n)
    col_hi = np.zeros(n)
    costs = np.zeros(n)
    for i, v in enumerate(variables):
        lb = -inf if v.lowBound is None else float(v.lowBound)
        ub = inf if v.upBound is None else float(v.upBound)
        if v.cat == pulp.LpBinary:
            lb, ub = 0.0, 1.0
        col_lo[i], col_hi[i] = lb, ub
    if problem.objective is not None:
        for v, coef in problem.objective.items():
            costs[index[id(v)]] = float(coef)

    h = highspy.Highs()
    h.silent()
    h.clear()
    try:
        h.resetGlobalScheduler(True)
    except TypeError:
        h.resetGlobalScheduler()
    h.addVars(n, col_lo, col_hi)
    for i, v in enumerate(variables):
        if v.cat in (pulp.LpInteger, pulp.LpBinary):
            h.changeColIntegrality(i, highspy.HighsVarType.kInteger)
        h.changeColCost(i, float(costs[i]))
    if problem.sense == pulp.LpMaximize:
        h.changeObjectiveSense(highspy.ObjSense.kMaximize)

    for cons in problem.constraints.values():
        inds = []
        vals = []
        for v, coef in cons.items():
            inds.append(index[id(v)])
            vals.append(float(coef))
        rhs = -float(cons.constant)
        if cons.sense == pulp.LpConstraintLE:
            lo, hi = -inf, rhs
        elif cons.sense == pulp.LpConstraintGE:
            lo, hi = rhs, inf
        else:
            lo, hi = rhs, rhs
        h.addRow(lo, hi, len(inds), np.asarray(inds, dtype=np.int32), np.asarray(vals, dtype=float))

    h.setOptionValue("time_limit", float(time_limit_s))
    h.setOptionValue("mip_rel_gap", float(mip_gap))
    h.setOptionValue("threads", int(max(threads, 1)))
    h.run()

    sol = h.getSolution()
    col_val = list(sol.col_value)
    if len(col_val) != n:
        raise RuntimeError(f"HiGHS returned {len(col_val)} columns, expected {n}")
    for i, v in enumerate(variables):
        v.varValue = float(col_val[i])

    model_status = h.getModelStatus()
    if model_status == highspy.HighsModelStatus.kOptimal:
        problem.status = pulp.LpStatusOptimal
        return pulp.LpStatusOptimal
    if model_status == highspy.HighsModelStatus.kInfeasible:
        problem.status = pulp.LpStatusInfeasible
        return pulp.LpStatusInfeasible
    if any(v.varValue is not None for v in variables):
        problem.status = pulp.LpStatusOptimal
        return pulp.LpStatusOptimal
    problem.status = pulp.LpStatusNotSolved
    return pulp.LpStatusNotSolved

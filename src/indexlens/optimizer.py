"""Training-only greedy support selection and capped, fully invested least squares.

L1 regularization cannot create sparsity on a long-only simplex: ||w||_1 = 1.
We therefore explicitly limit the support, then solve a small convex problem.
This heuristic does not claim the global cardinality-constrained optimum.
"""

import math
import numpy as np
from scipy.optimize import minimize


def fit_weights(x: np.ndarray, y: np.ndarray, max_weight: float = .25,
                ridge: float = 1e-4) -> np.ndarray:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y) or len(y) < 2:
        raise ValueError("Expected aligned 2-D returns and a 1-D benchmark.")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Non-finite training observations.")
    k = x.shape[1]
    if not 0 < max_weight <= 1 or k * max_weight < 1 - 1e-10 or ridge < 0:
        raise ValueError("Infeasible position cap or invalid regularization.")
    # Scaling daily returns to percentage points improves SLSQP conditioning.
    a, b = x * 100, y * 100
    gram = a.T @ a / len(a) + ridge * np.eye(k)
    cross = a.T @ b / len(a)
    result = minimize(lambda w: float(w @ gram @ w - 2 * cross @ w),
                      np.full(k, 1 / k), jac=lambda w: 2 * (gram @ w - cross),
                      method="SLSQP", bounds=[(0, max_weight)] * k,
                      constraints={"type": "eq", "fun": lambda w: w.sum() - 1,
                                   "jac": lambda w: np.ones(k)},
                      options={"ftol": 1e-11, "maxiter": 500})
    if not result.success:
        raise RuntimeError(f"Constrained fit failed: {result.message}")
    w = np.maximum(result.x, 0)
    w /= w.sum()
    if np.any(w > max_weight + 1e-7) or abs(w.sum() - 1) > 1e-8:
        raise RuntimeError("Solver returned invalid portfolio weights.")
    return w


def sparse_path(x: np.ndarray, y: np.ndarray, budgets: list[int],
                max_weight: float = .25) -> dict[int, list[int]]:
    """Build nested supports using ONLY training data, with deterministic ties."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if not 0 < max_weight <= 1:
        raise ValueError("Position cap must be in (0, 1].")
    if not budgets or max(budgets) > x.shape[1]:
        raise ValueError("Holding budgets must fit the eligible universe.")
    minimum = math.ceil(1 / max_weight - 1e-10)
    if min(budgets) < minimum or any(k != int(k) for k in budgets):
        raise ValueError("Holding budget is infeasible for the position cap.")
    norms = np.linalg.norm(x, axis=0)
    score = (x.T @ y) / np.maximum(norms, 1e-12)
    selected = list(np.argsort(-score, kind="stable")[:minimum])
    path = {}
    while len(selected) <= max(budgets):
        weights = fit_weights(x[:, selected], y, max_weight)
        if len(selected) in budgets:
            path[len(selected)] = selected.copy()
        if len(selected) == max(budgets):
            break
        fitted = x[:, selected] @ weights
        residual = y - fitted
        directions = x - fitted[:, None]
        gains = (directions.T @ residual) / np.maximum(np.linalg.norm(directions, axis=0), 1e-12)
        gains[selected] = -np.inf
        selected.append(int(np.argmax(gains)))
    return path


def choose_budget(scores: dict[int, float], complexity_weight: float = .5) -> int:
    """Closest validation point to the ideal (smallest budget, lowest error).

    Normalize each axis to [0, 1] over the tested grid, then minimize squared
    distance. Equal weight is a declared preference, not a statistical optimum.
    If accuracy is identical, choose the smallest portfolio. No test data enters.
    """
    if not scores or not 0 < complexity_weight < 1:
        raise ValueError("Invalid selection scores or complexity weight.")
    if any(not np.isfinite(v) or v < 0 for v in scores.values()):
        raise ValueError("Selection scores must be finite and non-negative.")
    ks = sorted(scores)
    error_span = max(scores.values()) - min(scores.values())
    if len(ks) == 1 or error_span < 1e-12:
        return ks[0]
    def distance(k):
        size = (k - ks[0]) / (ks[-1] - ks[0])
        error = (scores[k] - min(scores.values())) / error_span
        return complexity_weight * size**2 + (1 - complexity_weight) * error**2
    return min(ks, key=lambda k: (distance(k), k))


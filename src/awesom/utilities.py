"""
Utilities for self.organizing maps.
"""

import itertools
from typing import Iterable, Iterator

import numpy as np
from scipy.spatial import distance
from scipy import stats

from . typealias import Array, Metric, SomDims


def grid_iter(n_rows: int, n_cols: int) -> Iterator[tuple[int, int]]:
    """Compute grid indices of an two-dimensional array.

    Args:
        n_rows:  Number of array rows.
        n_cols:  Number of array columns.

    Returns:
        Multi-index iterator.
    """
    return itertools.product(range(n_rows), range(n_cols))


def grid(n_rows: int, n_cols: int) -> Array:
    """Compute grid indices of a two-dimensional array.

    Args:
        n_rows:  Number of array rows.
        n_cols:  Number of array columns.

    Returns:
        Two-dimensional array in which each row represents an multi-index.
    """
    return np.array(list(grid_iter(n_rows, n_cols)))


def decrease_linear(start: float, step: float, stop: float = 1.0
                    ) -> Iterator[float]:
    """Linearily decrease ``start``  in ``step`` steps to ``stop``."""
    if step < 1 or not isinstance(step, int):
        raise ValueError("Param `step` must be int >= 1.")
    if step == 1:
        yield start
    else:
        coef = (stop - start) / (step - 1)
        for stp in range(step):
            yield coef * stp + start


def decrease_expo(start: float, step: float, stop: float = 1.0
                  ) -> Iterator[float]:
    """Exponentially decrease ``start``  in ``step`` steps to ``stop``."""
    if step < 1 or not isinstance(step, int):
        raise ValueError("Param `step` must be int >= 1.")
    if step == 1:
        yield start
    else:
        coef = np.log(stop / start) / (step - 1)
        for stp in range(step):
            yield start * np.exp(coef*stp)


def best_match(weights: Array, inp: Array, metric: Metric
               ) -> tuple[Array, Array]:
    """Compute the best matching unit of ``weights`` for each
    element in ``inp``.

    If several elemets in ``weights`` have the same distance to the
    current element of ``inp``, the first element of ``weights`` is
    choosen to be the best matching unit.

    Args:
        weights:    Two-dimensional array of weights, in which each row
                    represents an unit.
        inp:        Array of test vectors. If two-dimensional, rows are
                    assumed to represent observations.
        metric:     Distance metric to use.

    Returns:
        Index and error of best matching units.
    """
    if weights.ndim != 2:
        msg = (f"Array ``weights`` has {weights.ndim} dimensions, it "
               "has to have exactly two dimensions.")
        raise ValueError(msg)

    if weights.shape[-1] != inp.shape[-1]:
        msg = (f"Feature dimension of ``weights`` has {weights.shape[0]} "
               "elemets, whereas ``inp`` has {inp.shape[-1]} elemets. "
               "However, both dimensions have to match exactly.")
        raise ValueError(msg)

    inp = np.atleast_2d(inp)
    if inp.ndim > 2:
        msg = (f"Array ``inp`` has {weights.ndim} dimensions, it "
               "has to have one or two dimensions.")
        raise ValueError(msg)

    dists = distance.cdist(weights, inp, metric)
    return dists.argmin(axis=0), dists.min(axis=0)


def sample_pca(dims: SomDims, data: Array | None = None, **kwargs) -> Array:
    """Compute initial SOM weights by sampling from the first two principal
    components of the input data.

    Args:
        dims:   Dimensions of SOM.
        data:   Input data set.
        adapt:  If ``True``, the largest value of ``shape`` is applied to the
                principal component with the largest sigular value. This
                orients the map, such that map dimension with the most units
                coincides with principal component with the largest variance.

    Returns:
        Array of SOM weights.
    """
    n_rows, n_cols, n_feats = dims

    if data is None:
        data = np.random.randint(-100, 100, (300, n_feats))
    _, vects, trans_data = pca(data, 2)
    data_min = trans_data.min(axis=0)
    data_max = trans_data.max(axis=0)
    if "adapt" in kwargs and kwargs['adapt'] is True:
        shape = tuple(sorted((n_rows, n_cols), reverse=True))
    else:
        shape = (n_rows, n_cols)
    dim_x = np.linspace(data_min[0], data_max[0], shape[0])
    dim_y = np.linspace(data_min[1], data_max[1], shape[1])
    grid_x, grid_y = np.meshgrid(dim_x, dim_y)
    points = np.vstack((grid_x.ravel(), grid_y.ravel()))
    weights = points.T @ vects + data.mean(axis=0)
    return weights


def sample_rnd(dims: SomDims, data: Array | None = None) -> Array:
    """Compute initial SOM weights by sampling uniformly from the data space.

    Args:
        dims:  Dimensions of SOM.
        data:  Input data set. If ``None``, sample from [-10, 10].

    Returns:
        Array of SOM weights.
    """
    n_rows, n_cols, n_feats = dims
    n_units = n_rows * n_cols
    if data is not None:
        data_limits = np.column_stack((data.min(axis=0), data.max(axis=0)))
    else:
        data_limits = np.random.randint(-10, 10, (n_feats, 2))
        data_limits.sort()
    weights = [np.random.uniform(dmin, dmax, n_units)
               for (dmin, dmax) in data_limits]
    return np.column_stack(weights)


def sample_stm(dims: SomDims, data: Array | None = None) -> Array:
    """Compute initial SOM weights by sampling stochastic matrices from
    Dirichlet distribution.

    The rows of each n by n stochastic matrix are sampes drawn from the
    Dirichlet distribution, where n is the number of rows and cols of the
    matrix. The diagonal elemets of the matrices are set to twice the
    probability of the remaining elements.
    The square root of the weight vectors' size must be a real integer.

    Args:
        dims:  Dimensions of SOM.
        data:  Input data set.

    Returns:
        Array of SOM weights.

    Notes:
        Each row of the output array is to be considered a flattened
        stochastic matrix, such that each ``N = sqrt(data.shape[1])`` values
        are a discrete probability distribution forming the ``N`` th row of
        the matrix.
    """
    n_rows, n_cols, n_feats = dims
    n_states = np.sqrt(n_feats)
    if bool(n_states - int(n_states)):
        msg = (f"Weight vector with {n_feats} elements is not "
               "reshapeable to square matrix.")
        raise ValueError(msg)

    n_states = int(n_states)
    n_units = n_rows * n_cols
    alpha = np.random.randint(1, 10, (n_states, n_states))
    st_matrix = np.hstack([stats.dirichlet(a).rvs(size=n_units)
                           for a in alpha])
    return st_matrix


def sample_hist(dims: SomDims, data: Array | None = None) -> Array:
    """Sample sum-normalized histograms.

    Args:
        dims:  Dimensions of SOM.
        data:  Input data set.

    Returns:
        Two-dimensional array in which each row is a historgram.
    """
    n_rows, n_cols, n_feats = dims
    return stats.dirichlet(np.ones(n_feats)).rvs(n_rows*n_cols)


def distribute(bmu_idx: Iterable[int], n_units: int
               ) -> dict[int, list[int]]:
    """List training data matches per SOM unit.

    This method assumes that the ith element of ``bmu_idx`` corresponds to the
    ith vetor in a array of input data vectors.

    Empty units result in empty list.

    Args:
        bmu_idx:  Indices of best matching units.
        n_units:  Number of units on the SOM.

    Returns:
        Dictionary in which the keys represent the flat indices of SOM units.
        The corresponding value is a list of indices of those training data
        vectors that have been mapped to this unit.
    """
    unit_matches: dict[int, list[int]] = {i: [] for i in range(n_units)}
    for data_idx, bmu in enumerate(bmu_idx):
        unit_matches[bmu].append(data_idx)
    return unit_matches


def pca(data: Array, n_comps: int = 2) -> tuple[Array, Array, Array]:
    """Perfom principal component analysis

    Interanlly, ``data`` will be centered but not scaled.

    Args:
        data:     Data set
        n_comps:  Number of principal components

    Returns:
        ``n_comps`` largest singular values,
        ``n_comps`` largest eigen vectors,
        transformed input data.
    """
    data_centered = (data - data.mean(axis=0))
    _, vals, vects = np.linalg.svd(data_centered)

    ord_idx = np.flip(vals.argsort())[:n_comps]
    vals = vals[ord_idx]
    vects = vects[ord_idx]
    return vals, vects, data_centered @ vects.T


def scale(arr: Array, new_min: int = 0, new_max: int = 1, axis: int = -1
          ) -> Array:
    """Scale ``arr`` between ``new_min`` and ``new_max``

    Args:
        arr:        Array to be scaled.
        new_min:    Lower bound.
        new_max:    Upper bound.

    Return:
        One-dimensional array of transformed values.
    """
    xmax = arr.max(axis=axis, keepdims=True)
    xmin = arr.min(axis=axis, keepdims=True)

    fact = (arr-xmin) / (xmax - xmin)
    out = fact * (new_max - new_min) + new_min

    return out


weight_initializer = {
    'rnd': sample_rnd,
    'stm': sample_stm,
    'pca': sample_pca,
    'hist': sample_hist}

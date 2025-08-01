import csv
import itertools
import os
import re
from collections.abc import Sequence
from contextlib import contextmanager, suppress
from glob import glob
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import dask.array as da
import imageio.v3 as iio
import numpy as np
from dask import delayed

from napari.utils.misc import abspath_or_url
from napari.utils.notifications import notification_manager
from napari.utils.translations import trans

if TYPE_CHECKING:
    from napari import Viewer
    from napari.types import FullLayerData, LayerData, ReaderFunction


def _alphanumeric_key(s: str) -> list[str | int]:
    """Convert string to list of strings and ints that gives intuitive sorting."""
    return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', s)]


URL_REGEX = re.compile(r'https?://|ftps?://|file://|file:\\')

_DROPPED_SCRIPTS_NAMESPACE = {}
# This is a global dictionary to store the namespace for scripts that are
# executed using drag and drop or the Python file reader.
# The content is a mapping from the script path to the namespace.
# The dict should not be overwritten but only modified, as
# it may be broken the execution of scripts that are already running.


def _is_url(filename):
    """Return True if string is an http or ftp path.

    Originally vendored from scikit-image/skimage/io/util.py
    """
    return isinstance(filename, str) and URL_REGEX.match(filename) is not None


def imread(filename: str) -> np.ndarray:
    """Dispatch reading images to imageio.v3 imread.

    Parameters
    ----------
    filename : string
        The path or URI from which to read the image.

    Returns
    -------
    data : np.ndarray
        The image data.
    """
    filename = abspath_or_url(filename)
    ext = os.path.splitext(filename)[1]

    if ext.lower() in ('.npy',):
        return np.load(filename)

    return iio.imread(str(filename))


def _guess_zarr_path(path: str) -> bool:
    """Guess whether string path is part of a zarr hierarchy."""
    return any(part.endswith('.zarr') for part in Path(path).parts)


def read_zarr_dataset(path: str):
    """Read a zarr dataset, including an array or a group of arrays.

    Parameters
    ----------
    path : str
        Path to directory ending in '.zarr'. Path can contain either an array
        or a group of arrays in the case of multiscale data.

    Returns
    -------
    image : array-like
        Array or list of arrays
    shape : tuple
        Shape of array or first array in list
    """
    path = Path(path)
    if (path / '.zarray').exists():
        # load zarr array
        image = da.from_zarr(path)
        shape = image.shape
    elif (path / '.zgroup').exists():
        # else load zarr all arrays inside file, useful for multiscale data
        image = [
            read_zarr_dataset(subpath)[0]
            for subpath in sorted(path.iterdir())
            if not subpath.name.startswith('.') and subpath.is_dir()
        ]
        assert image, 'No arrays found in zarr group'
        shape = image[0].shape
    elif (path / 'zarr.json').exists():
        # zarr v3
        import zarr

        data = zarr.open(store=path)
        if isinstance(data, zarr.Array):
            image = da.from_zarr(data)
            shape = image.shape
        else:
            image = [data[k] for k in sorted(data)]
            assert image, 'No arrays found in zarr group'
            shape = image[0].shape
    else:  # pragma: no cover
        raise ValueError(
            trans._(
                'Not a zarr dataset or group: {path}', deferred=True, path=path
            )
        )
    return image, shape


PathOrStr = Union[str, Path]


def magic_imread(
    filenames: PathOrStr | list[PathOrStr], *, use_dask=None, stack=True
):
    """Dispatch the appropriate reader given some files.

    The files are assumed to all have the same shape.

    Parameters
    ----------
    filenames : list
        List of filenames or directories to be opened.
        A list of `pathlib.Path` objects and a single filename or `Path` object
        are also accepted.
    use_dask : bool
        Whether to use dask to create a lazy array, rather than NumPy.
        Default of None will resolve to True if filenames contains more than
        one image, False otherwise.
    stack : bool
        Whether to stack the images in multiple files into a single array. If
        False, a list of arrays will be returned.

    Returns
    -------
    image : array-like
        Array or list of images
    """
    _filenames: list[str] = (
        [str(x) for x in filenames]
        if isinstance(filenames, list | tuple)
        else [str(filenames)]
    )
    if not _filenames:  # pragma: no cover
        raise ValueError('No files found')

    # replace folders with their contents
    filenames_expanded: list[str] = []
    for filename in _filenames:
        # zarr files are folders, but should be read as 1 file
        if (
            os.path.isdir(filename)
            and not _guess_zarr_path(filename)
            and not _is_url(filename)
        ):
            dir_contents = sorted(
                glob(os.path.join(filename, '*.*')), key=_alphanumeric_key
            )
            # remove subdirectories
            dir_contents_files = filter(
                lambda f: not os.path.isdir(f), dir_contents
            )
            filenames_expanded.extend(dir_contents_files)
        else:
            filenames_expanded.append(filename)

    if use_dask is None:
        use_dask = len(filenames_expanded) > 1

    if not filenames_expanded:
        raise ValueError(
            trans._(
                'No files found in {filenames} after removing subdirectories',
                deferred=True,
                filenames=filenames,
            )
        )

    # then, read in images
    images = []
    shape = None
    for filename in filenames_expanded:
        if _guess_zarr_path(filename):
            image, zarr_shape = read_zarr_dataset(filename)
            # 1D images are currently unsupported, so skip them.
            if len(zarr_shape) == 1:
                continue
            if shape is None:
                shape = zarr_shape
        else:
            if shape is None:
                image = imread(filename)
                shape = image.shape
                dtype = image.dtype
            if use_dask:
                image = da.from_delayed(
                    delayed(imread)(filename), shape=shape, dtype=dtype
                )
            elif len(images) > 0:  # not read by shape clause
                image = imread(filename)
        images.append(image)

    if not images:
        return None

    if len(images) == 1:
        image = images[0]
    elif stack:
        if use_dask:
            image = da.stack(images)
        else:
            try:
                image = np.stack(images)
            except ValueError as e:
                if 'input arrays must have the same shape' in str(e):
                    msg = trans._(
                        'To stack multiple files into a single array with numpy, all input arrays must have the same shape. Set `use_dask` to True to stack arrays with different shapes.',
                        deferred=True,
                    )
                    raise ValueError(msg) from e
                raise  # pragma: no cover
    else:
        image = images  # return a list
    return image


def _points_csv_to_layerdata(
    table: np.ndarray, column_names: list[str]
) -> 'FullLayerData':
    """Convert table data and column names from a csv file to Points LayerData.

    Parameters
    ----------
    table : np.ndarray
        CSV data.
    column_names : list of str
        The column names of the csv file

    Returns
    -------
    layer_data : tuple
        3-tuple ``(array, dict, str)`` (points data, metadata, 'points')
    """

    data_axes = [cn.startswith('axis-') for cn in column_names]
    data = np.array(table[:, data_axes]).astype('float')

    # Add properties to metadata if provided
    prop_axes = np.logical_not(data_axes)
    if column_names[0] == 'index':
        prop_axes[0] = False
    meta: dict = {}
    if np.any(prop_axes):
        meta['properties'] = {}
        for ind in np.nonzero(prop_axes)[0]:
            values = table[:, ind]
            try:
                values = np.array(values).astype('int')
            except ValueError:
                with suppress(ValueError):
                    values = np.array(values).astype('float')
            meta['properties'][column_names[ind]] = values

    return data, meta, 'points'


def _shapes_csv_to_layerdata(
    table: np.ndarray, column_names: list[str]
) -> 'FullLayerData':
    """Convert table data and column names from a csv file to Shapes LayerData.

    Parameters
    ----------
    table : np.ndarray
        CSV data.
    column_names : list of str
        The column names of the csv file

    Returns
    -------
    layer_data : tuple
        3-tuple ``(array, dict, str)`` (points data, metadata, 'shapes')
    """

    data_axes = [cn.startswith('axis-') for cn in column_names]
    raw_data = np.array(table[:, data_axes]).astype('float')

    inds = np.array(table[:, 0]).astype('int')
    n_shapes = max(inds) + 1
    # Determine when shape id changes
    transitions = list((np.diff(inds)).nonzero()[0] + 1)
    shape_boundaries = [0, *transitions] + [len(table)]
    if n_shapes != len(shape_boundaries) - 1:
        raise ValueError(
            trans._('Expected number of shapes not found', deferred=True)
        )

    data = []
    shape_type = []
    for ind_a, ind_b in itertools.pairwise(shape_boundaries):
        data.append(raw_data[ind_a:ind_b])
        shape_type.append(table[ind_a, 1])

    return data, {'shape_type': shape_type}, 'shapes'


def _guess_layer_type_from_column_names(
    column_names: list[str],
) -> str | None:
    """Guess layer type based on column names from a csv file.

    Parameters
    ----------
    column_names : list of str
        List of the column names from the csv.

    Returns
    -------
    str or None
        Layer type if recognized, otherwise None.
    """

    if {'index', 'shape-type', 'vertex-index', 'axis-0', 'axis-1'}.issubset(
        column_names
    ):
        return 'shapes'
    if {'axis-0', 'axis-1'}.issubset(column_names):
        return 'points'
    return None


def read_csv(
    filename: str, require_type: str | None = None
) -> tuple[np.ndarray, list[str], str | None]:
    """Return CSV data only if column names match format for ``require_type``.

    Reads only the first line of the CSV at first, then optionally raises an
    exception if the column names are not consistent with a known format, as
    determined by the ``require_type`` argument and
    :func:`_guess_layer_type_from_column_names`.

    Parameters
    ----------
    filename : str
        Path of file to open
    require_type : str, optional
        The desired layer type. If provided, should be one of the keys in
        ``csv_reader_functions`` or the string "any".  If ``None``, data, will
        not impose any format requirements on the csv, and data will always be
        returned.  If ``any``, csv must be recognized as one of the valid layer
        data formats, otherwise a ``ValueError`` will be raised.  If a specific
        layer type string, then a ``ValueError`` will be raised if the column
        names are not of the predicted format.

    Returns
    -------
    (data, column_names, layer_type) : Tuple[np.array, List[str], str]
        The table data and column names from the CSV file, along with the
        detected layer type (string).

    Raises
    ------
    ValueError
        If the column names do not match the format requested by
        ``require_type``.
    """
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        column_names = next(reader)

        layer_type = _guess_layer_type_from_column_names(column_names)
        if require_type:
            if not layer_type:
                raise ValueError(
                    trans._(
                        'File "{filename}" not recognized as valid Layer data',
                        deferred=True,
                        filename=filename,
                    )
                )
            if layer_type != require_type and require_type.lower() != 'any':
                raise ValueError(
                    trans._(
                        'File "{filename}" not recognized as {require_type} data',
                        deferred=True,
                        filename=filename,
                        require_type=require_type,
                    )
                )

        data = np.array(list(reader))
    return data, column_names, layer_type


csv_reader_functions = {
    'points': _points_csv_to_layerdata,
    'shapes': _shapes_csv_to_layerdata,
}


def csv_to_layer_data(
    path: str, require_type: str | None = None
) -> Optional['FullLayerData']:
    """Return layer data from a CSV file if detected as a valid type.

    Parameters
    ----------
    path : str
        Path of file to open
    require_type : str, optional
        The desired layer type. If provided, should be one of the keys in
        ``csv_reader_functions`` or the string "any".  If ``None``,
        unrecognized CSV files will simply return ``None``.  If ``any``,
        unrecognized CSV files will raise a ``ValueError``.  If a specific
        layer type string, then a ``ValueError`` will be raised if the column
        names are not of the predicted format.

    Returns
    -------
    layer_data : tuple, or None
        3-tuple ``(array, dict, str)`` (points data, metadata, layer_type) if
        CSV is recognized as a valid type.

    Raises
    ------
    ValueError
        If ``require_type`` is not ``None``, but the CSV is not detected as a
        valid data format.
    """
    try:
        # pass at least require "any" here so that we don't bother reading the
        # full dataset if it's not going to yield valid layer_data.
        _require = require_type or 'any'
        table, column_names, _type = read_csv(path, require_type=_require)
    except ValueError:
        if not require_type:
            return None
        raise
    if _type in csv_reader_functions:
        return csv_reader_functions[_type](table, column_names)
    return None  # only reachable if it is a valid layer type without a reader


def _csv_reader(path: str | Sequence[str]) -> list['LayerData']:
    if isinstance(path, str):
        layer_data = csv_to_layer_data(path, require_type=None)
        return [layer_data] if layer_data else []
    return [
        layer_data
        for p in path
        if (layer_data := csv_to_layer_data(p, require_type=None))
    ]


def _magic_imreader(path: str) -> list['LayerData']:
    return [(magic_imread(path),)]


def napari_get_reader(
    path: str | list[str],
) -> 'ReaderFunction':
    """Our internal fallback file reader at the end of the reader plugin chain.

    This will assume that the filepath is an image, and will pass all of the
    necessary information to viewer.add_image().

    Parameters
    ----------
    path : str
        path to file/directory

    Returns
    -------
    callable
        function that returns layer_data to be handed to viewer._add_layer_data
    """
    if isinstance(path, str) and path.endswith('.csv'):
        return _csv_reader

    return _magic_imreader


@contextmanager
def _patch_viewer_new():
    """Context manager to patch the viewer's new method."""
    from napari.viewer import Viewer, current_viewer

    original_new = Viewer.__new__
    original_init = Viewer.__init__

    def patched_init(self, *args, **kwargs):
        Viewer.__init__ = original_init

    def patched_new(cls, *args, **kwargs):
        ndisplay = None
        if len(kwargs) == 1 and 'ndisplay' in kwargs:
            ndisplay = kwargs.pop('ndisplay')

        if not kwargs and not args:
            viewer = current_viewer()
            if ndisplay is not None:
                viewer.dims.ndisplay = ndisplay
            if viewer is not None:
                Viewer.__new__ = original_new
                return viewer
        Viewer.__init__ = original_init
        return original_new(cls)

    Viewer.__new__ = patched_new
    Viewer.__init__ = patched_init
    try:
        yield
    finally:
        Viewer.__new__ = original_new
        Viewer.__init__ = original_init


def filter_variables(variables: dict[str, Any]) -> dict[str, Any]:
    res = variables.copy()
    res.pop('viewer', None)
    return res


def _add_dropped_scripts_to_console(
    variables: dict[str, Any], viewer: 'Viewer | None'
) -> None:
    if viewer is None:
        return

    variables = filter_variables(variables)

    if viewer.window._qt_viewer._console is None:
        viewer.window._qt_viewer.add_to_console_backlog(variables)
    else:
        console = viewer.window._qt_viewer._console
        console.push(variables)


def load_and_execute_python_code(path: str) -> list['LayerData']:
    """Load and execute Python code from a file.

    Parameters
    ----------
    path : str
        Path to the Python file to be executed.
    """
    from napari.viewer import current_viewer

    code = Path(path).read_text()
    with _patch_viewer_new():
        try:
            viewer = current_viewer()
            exec(code, _DROPPED_SCRIPTS_NAMESPACE.setdefault(path, {}))
            _add_dropped_scripts_to_console(
                _DROPPED_SCRIPTS_NAMESPACE[path], viewer
            )
        except BaseException as e:  # noqa: BLE001
            notification_manager.receive_error(type(e), e, e.__traceback__)
    return [(None,)]


def napari_get_py_reader(path: str) -> 'ReaderFunction | None':
    """Return a reader function for Python files.

    This function is used to read Python files and execute their content.
    It returns a callable that executes the code in the file.

    Parameters
    ----------
    path : str
        Path to the Python file to be executed.

    Returns
    -------
    callable
        A function that executes the Python code in the specified file.
    """
    if not os.path.exists(path):
        return None
    if os.path.splitext(path)[1] != '.py':
        return None
    return load_and_execute_python_code

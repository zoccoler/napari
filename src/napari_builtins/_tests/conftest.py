from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from npe2 import DynamicPlugin, PluginManager, PluginManifest

import napari_builtins
from napari import layers


@pytest.fixture(autouse=True)
def mock_npe2_pm():
    """Mock plugin manager with no registered plugins."""
    with patch.object(PluginManager, 'discover'):
        _pm = PluginManager()
    with patch('npe2.PluginManager.instance', return_value=_pm):
        yield _pm


@pytest.fixture(autouse=True)
def use_builtins(mock_npe2_pm: PluginManager):
    plugin = DynamicPlugin('napari', plugin_manager=mock_npe2_pm)
    mf = PluginManifest.from_file(
        Path(napari_builtins.__file__).parent / 'builtins.yaml'
    )
    plugin.manifest = mf
    with plugin:
        yield plugin


LAYERS: list[tuple[str, list, dict]] = [
    ('Image', [np.random.rand(10, 10)], {}),
    ('Labels', [np.random.randint(0, 16000, (32, 32), 'uint64')], {}),
    ('Points', [np.random.rand(20, 2)], {}),
    # Another points layer with each point having a property called 'values' set to a random float
    (
        'Points',
        [np.random.rand(20, 2)],
        {'properties': {'values': np.random.rand(20)}},
    ),
    (
        'Shapes',
        [
            [
                [(0, 0), (1, 1)],
                [(5, 7), (10, 10)],
                [(1, 3), (2, 4), (3, 5), (4, 6), (5, 7), (6, 8)],
                [(4, 3), (5, -4), (6.1, 5), (7, 6.5), (8, 7), (9, 8)],
                [(5.4, 6.7), (1.2, -3)],
            ]
        ],
        {
            'shape_type': ['ellipse', 'line', 'path', 'polygon', 'rectangle'],
        },
    ),
]


@pytest.fixture(params=LAYERS)
def some_layer(request) -> layers.Layer:
    layer_name, args, kwargs = request.param
    return getattr(layers, layer_name)(*args, **kwargs)


@pytest.fixture
def layers_list() -> list[layers.Layer]:
    return [
        getattr(layers, layer_name)(*args, **kwargs)
        for layer_name, args, kwargs in LAYERS
    ]

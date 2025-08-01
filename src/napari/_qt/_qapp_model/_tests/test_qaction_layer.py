from unittest.mock import Mock

import numpy as np
import numpy.testing as npt
import pytest
from qtpy.QtWidgets import QApplication

from napari._qt._qapp_model.qactions._layerlist_context import (
    _copy_affine_to_clipboard,
    _copy_rotate_to_clipboard,
    _copy_scale_to_clipboard,
    _copy_shear_to_clipboard,
    _copy_spatial_to_clipboard,
    _copy_translate_to_clipboard,
    _copy_units_to_clipboard,
    _paste_spatial_from_clipboard,
    is_valid_spatial_in_clipboard,
)
from napari.components import LayerList
from napari.layers.base._test_util_sample_layer import SampleLayer
from napari.utils.transforms import Affine
from napari.utils.transforms._units import get_units_from_name


@pytest.fixture
def layer_list():
    layer_1 = SampleLayer(
        data=np.empty((10, 10)),
        scale=(2, 3),
        translate=(1, 1),
        rotate=90,
        name='l1',
        affine=Affine(scale=(0.5, 0.5), translate=(1, 2), rotate=45),
        shear=[1],
        units=('nm', 'um'),
    )
    layer_2 = SampleLayer(
        data=np.empty((10, 10)),
        scale=(1, 1),
        translate=(0, 0),
        rotate=0,
        name='l2',
        affine=Affine(),
        shear=[0],
    )
    layer_3 = SampleLayer(
        data=np.empty((10, 10)),
        scale=(1, 1),
        translate=(0, 0),
        rotate=0,
        name='l3',
        affine=Affine(),
        shear=[0],
    )

    ll = LayerList([layer_1, layer_2, layer_3])
    ll.selection = {layer_2}
    return ll


@pytest.fixture
def layer_list_dim():
    layer_1 = SampleLayer(
        data=np.empty((5, 10, 10)),
        scale=(2, 3, 4),
        translate=(1, 1, 2),
        rotate=90,
        name='l1',
        affine=Affine(scale=(0.1, 0.5, 0.5), translate=(4, 1, 2), rotate=45),
        shear=[1, 0.5, 1],
        units=('nm', 'um', 'mm'),
    )
    layer_2 = SampleLayer(
        data=np.empty((10, 10)),
        scale=(1, 1),
        translate=(0, 0),
        rotate=0,
        name='l2',
        affine=Affine(),
        shear=[0],
    )
    ll = LayerList([layer_1, layer_2])
    ll.selection = {layer_2}
    return ll


@pytest.fixture
def layer_list_dim2(layer_list_dim):
    layer_list_dim.selection = {layer_list_dim['l1'], layer_list_dim['l2']}
    return layer_list_dim


@pytest.mark.usefixtures('qtbot')
def test_copy_scale_to_clipboard(layer_list):
    """This is the test that checks copying scale to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has a non-default scale.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    It also checks if the translate is not copied.
    """
    _copy_scale_to_clipboard(layer_list['l1'])
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_equal(layer_list['l2'].scale, (2, 3))
    npt.assert_array_equal(layer_list['l3'].scale, (1, 1))
    npt.assert_array_equal(layer_list['l2'].translate, (0, 0))


@pytest.mark.usefixtures('qtbot')
def test_paste_scale_higher_dim(layer_list_dim2):
    """This is the test that checks copying scale to
    clipboard and pasting it to another layer with higher dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l2 is selected and l1 has a non-default scale.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    QApplication.clipboard().setText('{"scale": [5, 5]}')
    _paste_spatial_from_clipboard(layer_list_dim2)
    npt.assert_array_equal(layer_list_dim2['l2'].scale, (5, 5))
    npt.assert_array_equal(layer_list_dim2['l1'].scale, (1, 5, 5))


@pytest.mark.usefixtures('qtbot')
def test_copy_units_to_clipboard(layer_list):
    """This is the test that checks copying units to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has non-default units.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    it also checks if the scale is not copied.
    """
    _copy_units_to_clipboard(layer_list['l1'])
    npt.assert_array_equal(
        layer_list['l2'].units, get_units_from_name(('pixel', 'pixel'))
    )
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_equal(
        layer_list['l2'].units, get_units_from_name(('nm', 'um'))
    )
    npt.assert_array_equal(
        layer_list['l3'].units, get_units_from_name(('pixel', 'pixel'))
    )
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))


@pytest.mark.usefixtures('qtbot')
def test_paste_units_higher_dim(layer_list_dim2):
    """This is the test that checks copying scale to
    clipboard and pasting it to another layer with higher dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l2 is selected and l1 has a non-default scale.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    QApplication.clipboard().setText('{"units": ["nm", "nm"]}')
    _paste_spatial_from_clipboard(layer_list_dim2)
    npt.assert_array_equal(
        layer_list_dim2['l2'].units, get_units_from_name(('nm', 'nm'))
    )
    npt.assert_array_equal(
        layer_list_dim2['l1'].units, get_units_from_name(('px', 'nm', 'nm'))
    )


@pytest.mark.usefixtures('qtbot')
def test_copy_translate_to_clipboard(layer_list):
    """This is the test that checks of copying translate to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has non-default translate.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    It also checks if the scale is not copied.
    """
    _copy_translate_to_clipboard(layer_list['l1'])
    npt.assert_array_equal(layer_list['l2'].translate, (0, 0))
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_equal(layer_list['l2'].translate, (1, 1))
    npt.assert_array_equal(layer_list['l3'].translate, (0, 0))
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))


@pytest.mark.usefixtures('qtbot')
def test_paste_translate_higher_dim(layer_list_dim2):
    """This is the test that checks copying translate to
    clipboard and pasting it to another layer with higher dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l2 is selected and l1 has non-default translate.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    QApplication.clipboard().setText('{"translate": [5, 5]}')
    _paste_spatial_from_clipboard(layer_list_dim2)
    npt.assert_array_equal(layer_list_dim2['l2'].translate, (5, 5))
    npt.assert_array_equal(layer_list_dim2['l1'].translate, (0, 5, 5))


@pytest.mark.usefixtures('qtbot')
def test_copy_rotate_to_clipboard(layer_list):
    """This is the test that checks copying rotate to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has non-default rotate.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    It also checks if the scale is not copied.
    """
    _copy_rotate_to_clipboard(layer_list['l1'])
    npt.assert_array_almost_equal(layer_list['l2'].rotate, ([1, 0], [0, 1]))
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_almost_equal(layer_list['l2'].rotate, ([0, -1], [1, 0]))
    npt.assert_array_almost_equal(layer_list['l3'].rotate, ([1, 0], [0, 1]))
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))


@pytest.mark.usefixtures('qtbot')
def test_paste_rotate_higher_dim(layer_list_dim2):
    """This is the test that checks copying rotate to
    clipboard and pasting it to another layer with higher dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l2 is selected and l1 has non-default rotate.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    QApplication.clipboard().setText('{"rotate": [[0, -1], [1, 0]]}')
    _paste_spatial_from_clipboard(layer_list_dim2)
    npt.assert_array_almost_equal(
        layer_list_dim2['l2'].rotate, ([0, -1], [1, 0])
    )
    npt.assert_array_almost_equal(
        layer_list_dim2['l1'].rotate, ([1, 0, 0], [0, 0, -1], [0, 1, 0])
    )


@pytest.mark.usefixtures('qtbot')
def test_copy_affine_to_clipboard(layer_list):
    """This is the test that checks copying affine to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has non-default affine.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    It also checks if the scale is not copied.
    """
    _copy_affine_to_clipboard(layer_list['l1'])
    npt.assert_array_almost_equal(
        layer_list['l2'].affine.linear_matrix, Affine().linear_matrix
    )
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_almost_equal(
        layer_list['l2'].affine.linear_matrix,
        layer_list['l1'].affine.linear_matrix,
    )
    npt.assert_array_almost_equal(
        layer_list['l3'].affine.linear_matrix, Affine().linear_matrix
    )
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))


@pytest.mark.usefixtures('qtbot')
def test_paste_affine_higher_dim(layer_list_dim2):
    """This is the test that checks copying affine to
    clipboard and pasting it to another layer with higher dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l2 is selected and l1 has non-default affine.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    QApplication.clipboard().setText(
        '{"affine": [[0.5, 0, 1], [0, 0.5, 2], [0, 0, 1]]}'
    )
    _paste_spatial_from_clipboard(layer_list_dim2)
    npt.assert_array_almost_equal(
        layer_list_dim2['l2'].affine.affine_matrix,
        np.array([[0.5, 0, 1], [0, 0.5, 2], [0, 0, 1]]),
    )
    npt.assert_array_almost_equal(
        layer_list_dim2['l1'].affine.affine_matrix,
        np.array([[1, 0, 0, 0], [0, 0.5, 0, 1], [0, 0, 0.5, 2], [0, 0, 0, 1]]),
    )


@pytest.mark.usefixtures('qtbot')
def test_copy_shear_to_clipboard(layer_list):
    """This is the test that checks copying shear to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has non-default shear.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    It also checks if the scale is not copied.
    """
    _copy_shear_to_clipboard(layer_list['l1'])
    npt.assert_array_almost_equal(layer_list['l2'].shear, (0,))
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_almost_equal(layer_list['l2'].shear, (1,))
    npt.assert_array_almost_equal(layer_list['l3'].shear, (0,))
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))


@pytest.mark.usefixtures('qtbot')
def test_paste_shear_higher_dim(layer_list_dim2):
    """This is the test that checks copying shear to
    clipboard and pasting it to another layer with higher dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l2 is selected and l1 has non-default shear.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    QApplication.clipboard().setText('{"shear": [5]}')
    _paste_spatial_from_clipboard(layer_list_dim2)
    npt.assert_array_almost_equal(layer_list_dim2['l2'].shear, (5,))
    npt.assert_array_almost_equal(layer_list_dim2['l1'].shear, (0, 0, 5))


@pytest.mark.usefixtures('qtbot')
def test_copy_spatial_to_clipboard(layer_list):
    """This is the test that checks copying spatial to
    clipboard and pasting it to another layer.

    The layer_list contains three layers, l1, l2 and l3.
    The l2 is selected and l1 has non-default spatial metadata.
    The test copy it to from l1 to l2 and check if l3 is not affected.
    """
    _copy_spatial_to_clipboard(layer_list['l1'])
    npt.assert_array_equal(layer_list['l2'].scale, (1, 1))
    _paste_spatial_from_clipboard(layer_list)
    npt.assert_array_equal(layer_list['l2'].scale, (2, 3))
    npt.assert_array_equal(layer_list['l2'].translate, (1, 1))
    npt.assert_array_almost_equal(layer_list['l2'].rotate, ([0, -1], [1, 0]))
    npt.assert_array_almost_equal(
        layer_list['l2'].affine.affine_matrix,
        layer_list['l1'].affine.affine_matrix,
    )
    npt.assert_array_equal(
        layer_list['l2'].units, get_units_from_name(('nm', 'um'))
    )
    npt.assert_array_equal(layer_list['l3'].scale, (1, 1))


@pytest.mark.usefixtures('qtbot')
def test_copy_spatial_to_clipboard_different_dim(layer_list_dim):
    """This is the test that checks copying spatial
    information from layer with higher dimensionality to layer
    with lower dimensionality.

    The layer_list_dim contains two layers, l1 and l2.
    The l1 contains 3D data and l2 contains 2D data.
    The l2 is selected and l1 has non-default spatial metadata.
    """
    _copy_spatial_to_clipboard(layer_list_dim['l1'])
    npt.assert_array_equal(layer_list_dim['l2'].scale, (1, 1))
    _paste_spatial_from_clipboard(layer_list_dim)
    npt.assert_array_equal(layer_list_dim['l2'].scale, (3, 4))
    npt.assert_array_equal(layer_list_dim['l2'].translate, (1, 2))
    npt.assert_array_almost_equal(
        layer_list_dim['l2'].rotate, ([0, -1], [1, 0])
    )
    npt.assert_array_almost_equal(
        layer_list_dim['l2'].affine.affine_matrix,
        layer_list_dim['l1'].affine.affine_matrix[-3:, -3:],
    )
    npt.assert_array_equal(
        layer_list_dim['l2'].units, get_units_from_name(('um', 'mm'))
    )


def test_fail_copy_to_clipboard(monkeypatch):
    mock_clipboard = Mock(return_value=None)
    warning_mock = Mock()

    monkeypatch.setattr(QApplication, 'clipboard', mock_clipboard)
    monkeypatch.setattr(
        'napari._qt._qapp_model.qactions._layerlist_context.show_warning',
        warning_mock,
    )
    layer = SampleLayer(data=np.empty((10, 10)))

    _copy_scale_to_clipboard(layer)

    mock_clipboard.assert_called_once()
    warning_mock.assert_called_once_with('Cannot access clipboard')


def test_fail_copy_data_from_clipboard(monkeypatch, layer_list):
    mock_clipboard = Mock(return_value=None)
    warning_mock = Mock()

    monkeypatch.setattr(QApplication, 'clipboard', mock_clipboard)
    monkeypatch.setattr(
        'napari._qt._qapp_model.qactions._layerlist_context.show_warning',
        warning_mock,
    )

    _paste_spatial_from_clipboard(layer_list)

    mock_clipboard.assert_called_once()
    warning_mock.assert_called_once_with('Cannot access clipboard')


@pytest.mark.usefixtures('qtbot')
def test_fail_decode_text(monkeypatch, layer_list):
    warning_mock = Mock()
    monkeypatch.setattr(
        'napari._qt._qapp_model.qactions._layerlist_context.show_warning',
        warning_mock,
    )

    clip = QApplication.clipboard()

    clip.setText('aaaaa')
    _paste_spatial_from_clipboard(layer_list)

    warning_mock.assert_called_once_with('Cannot parse clipboard data')


@pytest.mark.usefixtures('qtbot')
def test_is_valid_spatial_in_clipboard_simple():
    layer = SampleLayer(data=np.empty((10, 10)))

    _copy_scale_to_clipboard(layer)
    assert is_valid_spatial_in_clipboard()


@pytest.mark.usefixtures('qtbot')
def test_is_valid_spatial_in_clipboard_json():
    QApplication.clipboard().setText('{"scale": [1, 1]}')
    assert is_valid_spatial_in_clipboard()


@pytest.mark.usefixtures('qtbot')
def test_is_valid_spatial_in_clipboard_bad_json():
    QApplication.clipboard().setText('[1, 1]')
    assert not is_valid_spatial_in_clipboard()


@pytest.mark.usefixtures('qtbot')
def test_is_valid_spatial_in_clipboard_invalid_str():
    QApplication.clipboard().setText('aaaa')
    assert not is_valid_spatial_in_clipboard()


@pytest.mark.usefixtures('qtbot')
def test_is_valid_spatial_in_clipboard_invalid_key():
    QApplication.clipboard().setText('{"scale": [1, 1], "invalid": 1}')
    assert not is_valid_spatial_in_clipboard()

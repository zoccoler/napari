# See "Writing benchmarks" in the asv docs for more information.
# https://asv.readthedocs.io/en/latest/writing_benchmarks.html
# or the napari documentation on benchmarking
# https://github.com/napari/napari/blob/main/docs/BENCHMARKS.md
from __future__ import annotations

import os

import numpy as np
from packaging.version import parse as parse_version
from qtpy.QtWidgets import QApplication

import napari
import napari.layers

NAPARI_0_4_19 = parse_version(napari.__version__) <= parse_version('0.4.19')


class QtViewerViewImageSuite:
    """Benchmarks for viewing images in the viewer."""

    data: np.ndarray
    viewer: napari.Viewer | None

    params = [2**i for i in range(4, 13)]

    if 'PR' in os.environ:
        skip_params = [(2**i,) for i in range(6, 13)]

    def setup(self, n):
        _ = QApplication.instance() or QApplication([])
        rng = np.random.default_rng(0)
        self.data = rng.random((n, n))
        self.viewer = None

    def teardown(self, n):
        self.viewer.window.close()

    def time_view_image(self, n):
        """Time to view an image."""
        self.viewer, _ = napari.imshow(self.data)


class QtViewerAddImageSuite:
    """Benchmarks for adding images to the viewer."""

    params = [2**i for i in range(4, 13)]

    if 'PR' in os.environ:
        skip_params = [(2**i,) for i in range(6, 13)]

    def setup(self, n):
        _ = QApplication.instance() or QApplication([])
        np.random.seed(0)
        self.data = np.random.random((n, n))
        self.viewer = napari.Viewer()

    def teardown(self, n):
        self.viewer.window.close()

    def time_add_image(self, n):
        """Time to view an image."""
        self.viewer.add_image(self.data)


class QtViewerImageSuite:
    """Benchmarks for images in the viewer."""

    viewer: napari.Viewer
    data: np.ndarray

    params = [2**i for i in range(4, 13)]

    if 'PR' in os.environ:
        skip_params = [(2**i,) for i in range(6, 13)]

    def setup(self, n):
        _ = QApplication.instance() or QApplication([])
        rng = np.random.default_rng(0)
        self.data = rng.random((n, n))
        self.viewer = napari.Viewer()
        self.viewer.add_image(self.data)

    def teardown(self, n):
        self.viewer.window.close()

    def time_zoom(self, n):
        """Time to zoom in and zoom out."""
        if NAPARI_0_4_19:
            self.viewer.window._qt_viewer.view.camera.zoom(
                0.5, center=(0.5, 0.5)
            )
            self.viewer.window._qt_viewer.view.camera.zoom(
                2.0, center=(0.5, 0.5)
            )
        else:
            self.viewer.window._qt_viewer.canvas.view.camera.zoom(
                0.5, center=(0.5, 0.5)
            )
            self.viewer.window._qt_viewer.canvas.view.camera.zoom(
                2.0, center=(0.5, 0.5)
            )

    def time_refresh(self, n):
        """Time to refresh view."""
        self.viewer.layers[0].refresh()

    def time_set_view_slice(self, n):
        """Time to set view slice."""
        self.viewer.layers[0]._set_view_slice()

    def time_update_thumbnail(self, n):
        """Time to update thumbnail."""
        self.viewer.layers[0]._update_thumbnail()

    def time_get_value(self, n):
        """Time to get current value."""
        self.viewer.layers[0].get_value((0,) * 2)


class QtViewerSingleImageSuite:
    """Benchmarks for a single image layer in the viewer."""

    data: np.ndarray
    new_data: np.ndarray
    viewer: napari.Viewer
    layer: napari.layers.Image

    def setup(self):
        _ = QApplication.instance() or QApplication([])
        rng = np.random.default_rng(0)
        self.data = rng.random((128, 128, 128))
        self.new_data = rng.random((128, 128, 128))
        self.viewer = napari.Viewer()
        self.layer = self.viewer.add_image(self.data)

    def teardown(self):
        self.viewer.window.close()

    def time_zoom(self):
        """Time to zoom in and zoom out."""
        if NAPARI_0_4_19:
            self.viewer.window._qt_viewer.view.camera.zoom(
                0.5, center=(0.5, 0.5)
            )
            self.viewer.window._qt_viewer.view.camera.zoom(
                2.0, center=(0.5, 0.5)
            )
        else:
            self.viewer.window._qt_viewer.canvas.view.camera.zoom(
                0.5, center=(0.5, 0.5)
            )
            self.viewer.window._qt_viewer.canvas.view.camera.zoom(
                2.0, center=(0.5, 0.5)
            )

    def time_set_data(self):
        """Time to set view slice."""
        self.layer.data = self.new_data

    def time_refresh(self):
        """Time to refresh view."""
        self.layer.refresh()

    def time_set_view_slice(self):
        """Time to set view slice."""
        self.layer._set_view_slice()

    def time_update_thumbnail(self):
        """Time to update thumbnail."""
        self.layer._update_thumbnail()

    def time_get_value(self):
        """Time to get current value."""
        self.layer.get_value((0,) * 3)

    def time_ndisplay(self):
        """Time to enter 3D rendering."""
        self.viewer.dims.ndisplay = 3


class QtViewerSingleInvisbleImageSuite:
    """Benchmarks for a invisible single image layer in the viewer."""

    data: np.ndarray
    new_data: np.ndarray
    viewer: napari.Viewer
    layer: napari.layers.Image

    def setup(self):
        _ = QApplication.instance() or QApplication([])
        rng = np.random.default_rng(0)
        self.data = rng.random((128, 128, 128))
        self.new_data = rng.random((128, 128, 128))
        self.viewer = napari.Viewer()
        self.layer = self.viewer.add_image(self.data, visible=False)

    def teardown(self):
        self.viewer.window.close()

    def time_zoom(self):
        """Time to zoom in and zoom out."""
        if NAPARI_0_4_19:
            self.viewer.window._qt_viewer.view.camera.zoom(
                0.5, center=(0.5, 0.5)
            )
            self.viewer.window._qt_viewer.view.camera.zoom(
                2.0, center=(0.5, 0.5)
            )
        else:
            self.viewer.window._qt_viewer.canvas.view.camera.zoom(
                0.5, center=(0.5, 0.5)
            )
            self.viewer.window._qt_viewer.canvas.view.camera.zoom(
                2.0, center=(0.5, 0.5)
            )

    def time_set_data(self):
        """Time to set view slice."""
        self.layer.data = self.new_data

    def time_refresh(self):
        """Time to refresh view."""
        self.layer.refresh()

    def time_set_view_slice(self):
        """Time to set view slice."""
        self.layer._set_view_slice()

    def time_update_thumbnail(self):
        """Time to update thumbnail."""
        self.layer._update_thumbnail()

    def time_get_value(self):
        """Time to get current value."""
        self.layer.get_value((0,) * 3)

    def time_ndisplay(self):
        """Time to enter 3D rendering."""
        self.viewer.dims.ndisplay = 3


class QtImageRenderingSuite:
    """Benchmarks for a single image layer in the viewer."""

    data: np.ndarray
    viewer: napari.Viewer
    layer: napari.layers.Image

    params = [2**i for i in range(4, 13)]

    if 'PR' in os.environ:
        skip_params = [(2**i,) for i in range(6, 13)]

    def setup(self, n):
        _ = QApplication.instance() or QApplication([])
        rng = np.random.default_rng(0)
        self.data = rng.random((n, n)) * 2**12
        self.viewer = napari.Viewer(ndisplay=2)
        self.layer = self.viewer.add_image(self.data)

    def teardown(self, n):
        self.viewer.close()

    def time_change_contrast(self, n):
        """Time to change contrast limits."""
        self.layer.contrast_limits = (250, 3000)
        self.layer.contrast_limits = (300, 2900)
        self.layer.contrast_limits = (350, 2800)

    def time_change_gamma(self, n):
        """Time to change gamma."""
        self.layer.gamma = 0.5
        self.layer.gamma = 0.8
        self.layer.gamma = 1.3


class QtVolumeRenderingSuite:
    """Benchmarks for a single image layer in the viewer."""

    data: np.ndarray
    viewer: napari.Viewer

    params = [2**i for i in range(4, 10)]

    if 'PR' in os.environ:
        skip_params = [(2**i,) for i in range(6, 10)]

    def setup(self, n):
        _ = QApplication.instance() or QApplication([])
        rng = np.random.default_rng(0)
        self.data = rng.random((n, n, n)) * 2**12
        self.viewer = napari.Viewer(ndisplay=3)
        self.viewer.add_image(self.data)

    def teardown(self, n):
        self.viewer.close()

    def time_change_contrast(self, n):
        """Time to change contrast limits."""
        self.viewer.layers[0].contrast_limits = (250, 3000)
        self.viewer.layers[0].contrast_limits = (300, 2900)
        self.viewer.layers[0].contrast_limits = (350, 2800)

    def time_change_gamma(self, n):
        """Time to change gamma."""
        self.viewer.layers[0].gamma = 0.5
        self.viewer.layers[0].gamma = 0.8
        self.viewer.layers[0].gamma = 1.3


if __name__ == '__main__':
    from utils import run_benchmark

    run_benchmark()

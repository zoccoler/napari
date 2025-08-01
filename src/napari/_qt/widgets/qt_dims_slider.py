import threading
from typing import TYPE_CHECKING
from weakref import ref

import numpy as np
from qtpy.QtCore import QObject, Qt, QThread, Signal, Slot
from qtpy.QtGui import QIntValidator
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from superqt import QElidingLineEdit

from napari._qt.dialogs.qt_modal import QtPopup
from napari._qt.utils import qt_signals_blocked
from napari._qt.widgets.qt_mirrored_sliders_popup import QMirroredSlidersPopup
from napari._qt.widgets.qt_scrollbar import ModifiedScrollBar
from napari.components import Dims
from napari.settings import get_settings
from napari.settings._constants import LoopMode
from napari.utils.events.event_utils import connect_setattr_value
from napari.utils.translations import trans

if TYPE_CHECKING:
    from napari._qt.widgets.qt_dims import QtDims


class _ModifiedScrollBar(ModifiedScrollBar):
    def mousePressEvent(self, event):
        """Update the slider, or, on right-click, pop-up the margin controls.

        Parameters
        ----------
        event : napari.utils.event.Event
            The napari event that triggered this method.
        """
        if event.button() == Qt.MouseButton.RightButton:
            self.parent().show_margins_popupup()
        else:
            super().mousePressEvent(event)


class QtDimSliderWidget(QWidget):
    """Compound widget to hold the label, slider and play button for an axis.

    These will usually be instantiated in the QtDims._create_sliders method.
    This widget *must* be instantiated with a parent QtDims.
    """

    fps_changed = Signal(float)
    mode_changed = Signal(str)
    range_changed = Signal(tuple)
    size_changed = Signal()
    play_started = Signal()
    play_stopped = Signal()
    margins_changed = Signal(float)

    def __init__(self, parent: QWidget, axis: int) -> None:
        super().__init__(parent=parent)
        self.axis = axis
        self.qt_dims: QtDims = parent
        self.dims: Dims = parent.dims
        self.axis_label = None
        self.slider = None
        self.play_button = None
        self.margins_popup = None
        self.curslice_label = QLineEdit(self)
        self.curslice_label.setToolTip(
            trans._('Current slice for axis {axis}', axis=axis)
        )
        # if we set the QIntValidator to actually reflect the range of the data
        # then an invalid (i.e. too large) index doesn't actually trigger the
        # editingFinished event (the user is expected to change the value)...
        # which is confusing to the user, so instead we use an IntValidator
        # that makes sure the user can only enter integers, but we do our own
        # value validation in self.change_slice
        self.curslice_label.setValidator(QIntValidator(0, 999999))

        self.curslice_label.editingFinished.connect(self._set_slice_from_label)
        self.totslice_label = QLabel(self)
        self.totslice_label.setToolTip(
            trans._('Total slices for axis {axis}', axis=axis)
        )
        self.curslice_label.setObjectName('slice_label')
        self.totslice_label.setObjectName('slice_label')
        sep = QFrame(self)
        sep.setFixedSize(1, 14)
        sep.setObjectName('slice_label_sep')

        settings = get_settings()
        self._fps = settings.application.playback_fps
        connect_setattr_value(
            settings.application.events.playback_fps, self, 'fps'
        )

        self._minframe = None
        self._maxframe = None
        self._loop_mode = settings.application.playback_mode
        connect_setattr_value(
            settings.application.events.playback_mode, self, 'loop_mode'
        )

        layout = QHBoxLayout()
        self._create_axis_label_widget()
        self._create_range_slider_widget()
        self._create_play_button_widget()

        layout.addWidget(self.axis_label)
        layout.addWidget(self.play_button)
        layout.addWidget(self.slider, stretch=2)
        layout.addWidget(self.curslice_label)
        layout.addWidget(sep)
        layout.addWidget(self.totslice_label)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(layout)
        self.dims.events.axis_labels.connect(self._pull_label)

    def _set_slice_from_label(self):
        """Update the dims point based on the curslice_label."""
        # On teardown some tests fail on OSX with an `IndexError`
        try:
            max_allowed = self.dims.nsteps[self.axis] - 1
        except IndexError:
            return

        val = int(self.curslice_label.text())
        if val > max_allowed:
            val = max_allowed
            self.curslice_label.setText(str(val))

        self.curslice_label.clearFocus()
        self.qt_dims.setFocus()
        self.dims.set_current_step(self.axis, val)

    def _create_axis_label_widget(self):
        """Create the axis label widget which accompanies its slider."""
        label = QElidingLineEdit(self)
        label.setObjectName('axis_label')  # needed for _update_label
        fm = label.fontMetrics()
        label.setEllipsesWidth(int(fm.averageCharWidth() * 3))
        label.setText(self.dims.axis_labels[self.axis])
        label.home(False)
        label.setToolTip(trans._('Edit to change axis label'))
        label.setAcceptDrops(False)
        label.setEnabled(True)
        label.setAlignment(Qt.AlignmentFlag.AlignRight)
        label.setContentsMargins(0, 0, 2, 0)
        label.textChanged.connect(self._update_label)
        label.editingFinished.connect(self._clear_label_focus)
        self.axis_label = label

    def _on_value_changed(self, value):
        """Slider changed to this new value.

        We split this out as a separate function for perfmon.
        """
        self.dims.set_current_step(self.axis, value)

    def _create_range_slider_widget(self):
        """Creates a range slider widget for a given axis."""
        # Set the maximum values of the range slider to be one step less than
        # the range of the layer as otherwise the slider can move beyond the
        # shape of the layer as the endpoint is included
        slider = _ModifiedScrollBar(Qt.Orientation.Horizontal)
        slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        slider.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        slider.setMinimum(0)
        slider.setMaximum(self.dims.nsteps[self.axis] - 1)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setValue(self.dims.current_step[self.axis])

        # Listener to be used for sending events back to model:
        slider.valueChanged.connect(self._on_value_changed)

        def slider_focused_listener():
            self.dims.last_used = self.axis

        # linking focus listener to the last used:
        slider.sliderPressed.connect(slider_focused_listener)
        self.slider = slider

    def show_margins_popupup(self):
        self.margins_popup = QMarginSlidersPopup(self.dims, self.axis, self)
        self.margins_popup.setParent(self)
        self.margins_popup.show_above_mouse()

    def _create_play_button_widget(self):
        """Creates the actual play button, which has the modal popup."""
        self.play_button = QtPlayButton(
            self.qt_dims, self.axis, fps=self._fps, mode=self._loop_mode
        )
        self.play_button.setToolTip(
            trans._('Right click on button for playback setting options.')
        )
        self.play_button.mode_combo.currentTextChanged.connect(
            lambda x: self.__class__.loop_mode.fset(
                self, LoopMode(x.replace(' ', '_'))
            )
        )

        def fps_listener(*args):
            fps = self.play_button.fpsspin.value()
            fps *= -1 if self.play_button.reverse_check.isChecked() else 1
            self.__class__.fps.fset(self, fps)

        self.play_button.fpsspin.editingFinished.connect(fps_listener)
        self.play_button.reverse_check.stateChanged.connect(fps_listener)
        self.play_stopped.connect(self.play_button._handle_stop)
        self.play_started.connect(self.play_button._handle_start)

    def _pull_label(self):
        """Updates the label LineEdit from the dims model."""
        label = self.dims.axis_labels[self.axis]
        self.axis_label.setText(label)

    def _update_label(self):
        """Update dimension slider label."""
        self.dims.set_axis_label(self.axis, self.axis_label.text())

    def _clear_label_focus(self):
        """Clear focus from dimension slider label."""
        self.axis_label.clearFocus()
        self.qt_dims.setFocus()

    def _update_range(self):
        """Updates range for slider."""
        displayed_sliders = self.qt_dims._displayed_sliders

        nsteps = self.dims.nsteps[self.axis] - 1
        if nsteps == 0:
            displayed_sliders[self.axis] = False
            self.qt_dims.last_used = 0
            self.hide()
        else:
            if (
                not displayed_sliders[self.axis]
                and self.axis not in self.dims.displayed
            ):
                displayed_sliders[self.axis] = True
                self.last_used = self.axis
                self.show()
            self.slider.setMinimum(0)
            self.slider.setMaximum(nsteps)
            self.slider.setSingleStep(1)
            self.slider.setPageStep(1)
            self.slider.setValue(self.dims.current_step[self.axis])
            self.totslice_label.setText(str(nsteps))
            self.totslice_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self._update_slice_labels()

            if self.margins_popup:
                self.margins_popup._reset_sliders()

    def _update_slider(self):
        """Update dimension slider."""
        self.slider.setValue(self.dims.current_step[self.axis])
        self._update_slice_labels()

    def _update_slice_labels(self):
        """Update slice labels to match current dimension slider position."""
        self.curslice_label.setText(str(self.dims.current_step[self.axis]))
        self.curslice_label.setAlignment(Qt.AlignmentFlag.AlignRight)

    @property
    def fps(self):
        """Frames per second for animation."""
        return self._fps

    @fps.setter
    def fps(self, value):
        """Frames per second for animation.

        Parameters
        ----------
        value : float
            Frames per second for animation.
        """
        if self._fps == value:
            return
        self._fps = value
        self.play_button.fpsspin.setValue(abs(value))
        self.play_button.reverse_check.setChecked(value < 0)
        self.fps_changed.emit(value)

    @property
    def loop_mode(self):
        """Loop mode for animation.

        Loop mode enumeration napari._qt._constants.LoopMode
        Available options for the loop mode string enumeration are:
        - LoopMode.ONCE
            Animation will stop once movie reaches the max frame
            (if fps > 0) or the first frame (if fps < 0).
        - LoopMode.LOOP
            Movie will return to the first frame after reaching
            the last frame, looping continuously until stopped.
        - LoopMode.BACK_AND_FORTH
            Movie will loop continuously until stopped,
            reversing direction when the maximum or minimum frame
            has been reached.
        """
        return self._loop_mode

    @loop_mode.setter
    def loop_mode(self, value):
        """Loop mode for animation.

        Parameters
        ----------
        value : napari._qt._constants.LoopMode
            Loop mode for animation.
            Available options for the loop mode string enumeration are:
            - LoopMode.ONCE
                Animation will stop once movie reaches the max frame
                (if fps > 0) or the first frame (if fps < 0).
            - LoopMode.LOOP
                Movie will return to the first frame after reaching
                the last frame, looping continuously until stopped.
            - LoopMode.BACK_AND_FORTH
                Movie will loop continuously until stopped,
                reversing direction when the maximum or minimum frame
                has been reached.
        """
        value = LoopMode(value)
        self._loop_mode = value
        self.play_button.mode_combo.setCurrentText(
            str(value).replace('_', ' ')
        )
        self.mode_changed.emit(str(value))

    @property
    def frame_range(self):
        """Frame range for animation, as (minimum_frame, maximum_frame)."""
        frame_range = (self._minframe, self._maxframe)
        frame_range = frame_range if any(frame_range) else None
        return frame_range

    @frame_range.setter
    def frame_range(self, value):
        """Frame range for animation, as (minimum_frame, maximum_frame).

        Parameters
        ----------
        value : tuple(int, int)
            Frame range as tuple/list with range (minimum_frame, maximum_frame)
        """
        if not isinstance(value, tuple | list | type(None)):
            raise TypeError(
                trans._('frame_range value must be a list or tuple')
            )

        if value and len(value) != 2:
            raise ValueError(trans._('frame_range must have a length of 2'))

        if value is None:
            value = (None, None)

        self._minframe, self._maxframe = value
        self.range_changed.emit(tuple(value))

    def _update_play_settings(self, fps, loop_mode, frame_range):
        """Update settings for animation.

        Parameters
        ----------
        fps : float
            Frames per second to play the animation.
        loop_mode : napari._qt._constants.LoopMode
            Loop mode for animation.
            Available options for the loop mode string enumeration are:
            - LoopMode.ONCE
                Animation will stop once movie reaches the max frame
                (if fps > 0) or the first frame (if fps < 0).
            - LoopMode.LOOP
                Movie will return to the first frame after reaching
                the last frame, looping continuously until stopped.
            - LoopMode.BACK_AND_FORTH
                Movie will loop continuously until stopped,
                reversing direction when the maximum or minimum frame
                has been reached.
        frame_range : tuple(int, int)
            Frame range as tuple/list with range (minimum_frame, maximum_frame)
        """
        if fps is not None:
            self.fps = fps
        if loop_mode is not None:
            self.loop_mode = loop_mode
        if frame_range is not None:
            self.frame_range = frame_range

    def resizeEvent(self, event):
        """Emit a signal to inform about a size change."""
        self.size_changed.emit()
        super().resizeEvent(event)


class QtCustomDoubleSpinBox(QDoubleSpinBox):
    """Custom Spinbox that emits an additional editingFinished signal whenever
    the valueChanged event is emitted AND the left mouse button is down.

    The original use case here was the FPS spinbox in the play button, where
    hooking to the actual valueChanged event is undesirable, because if the
    user clears the LineEdit to type, for example, "0.5", then play back
    will temporarily pause when "0" is typed (if the animation is currently
    running).  However, the editingFinished event ignores mouse click events on
    the spin buttons.  This subclass class triggers an event both during
    editingFinished and when the user clicks on the spin buttons.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, *kwargs)
        self.valueChanged.connect(self.custom_change_event)

    def custom_change_event(self, value):
        """Emits editingFinished if valueChanged AND left mouse button is down.
        (i.e. when the user clicks on the spin buttons)
        Paramters
        ---------
        value : float
            The value of this custom double spin box.
        """
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self.editingFinished.emit()

    def textFromValue(self, value):
        """This removes the decimal places if the float is an integer.

        Parameters
        ----------
        value : float
            The value of this custom double spin box.
        """
        if value.is_integer():
            value = int(value)
        return str(value)

    def keyPressEvent(self, event):
        """Handle key press event for the dimension slider spinbox.

        Parameters
        ----------
        event : qtpy.QtCore.QKeyEvent
            Event from the Qt context.
        """
        # this is here to intercept Return/Enter keys when editing the FPS
        # SpinBox.  We WANT the return key to close the popup normally,
        # but if the user is editing the FPS spinbox, we simply want to
        # register the change and lose focus on the lineEdit, in case they
        # want to make an additional change (without reopening the popup)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.editingFinished.emit()
            self.clearFocus()
            return
        super().keyPressEvent(event)


class QtPlayButton(QPushButton):
    """Play button, included in the DimSliderWidget, to control playback

    the button also owns the QtModalPopup that controls the playback settings.
    """

    play_requested = Signal(int)  # axis, fps

    def __init__(
        self, qt_dims, axis, reverse=False, fps=10, mode=LoopMode.LOOP
    ) -> None:
        super().__init__()
        self.qt_dims_ref = ref(qt_dims)
        self.axis = axis
        self.reverse = reverse
        self.fps = fps
        self.mode = mode
        self.setProperty('reverse', str(reverse))  # for styling
        self.setProperty('playing', 'False')  # for styling

        # build popup modal form

        self.popup = QtPopup(self)
        form_layout = QFormLayout()
        self.popup.frame.setLayout(form_layout)

        fpsspin = QtCustomDoubleSpinBox(self.popup)
        fpsspin.setObjectName('fpsSpinBox')
        fpsspin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fpsspin.setValue(self.fps)
        if hasattr(fpsspin, 'setStepType'):
            # this was introduced in Qt 5.12.  Totally optional, just nice.
            fpsspin.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        fpsspin.setMaximum(500)
        fpsspin.setMinimum(0)
        form_layout.insertRow(
            0,
            QLabel(trans._('frames per second:'), parent=self.popup),
            fpsspin,
        )
        self.fpsspin = fpsspin

        revcheck = QCheckBox(self.popup)
        revcheck.setObjectName('playDirectionCheckBox')
        form_layout.insertRow(
            1, QLabel(trans._('play direction:'), parent=self.popup), revcheck
        )
        self.reverse_check = revcheck

        mode_combo = QComboBox(self.popup)
        mode_combo.addItems([str(i).replace('_', ' ') for i in LoopMode])
        form_layout.insertRow(
            2, QLabel(trans._('play mode:'), parent=self.popup), mode_combo
        )
        mode_combo.setCurrentText(str(self.mode).replace('_', ' '))
        self.mode_combo = mode_combo

    def mouseReleaseEvent(self, event):
        """Show popup for right-click, toggle animation for right click.

        Parameters
        ----------
        event : qtpy.QtCore.QMouseEvent
            Event from the qt context.
        """
        # using this instead of self.customContextMenuRequested.connect and
        # clicked.connect because the latter was not sending the
        # rightMouseButton release event.
        if event.button() == Qt.MouseButton.RightButton:
            self.popup.show_above_mouse()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._on_click()

    def _on_click(self):
        """Toggle play/stop animation control."""
        qt_dims = self.qt_dims_ref()
        if not qt_dims:  # pragma: no cover
            return None
        if self.property('playing') == 'True':
            return qt_dims.stop()
        self.play_requested.emit(self.axis)
        return None

    def _handle_start(self):
        """On animation start, set playing property to True & update style."""
        self.setProperty('playing', 'True')
        self.style().unpolish(self)
        self.style().polish(self)

    def _handle_stop(self):
        """On animation stop, set playing property to False & update style."""
        self.setProperty('playing', 'False')
        self.style().unpolish(self)
        self.style().polish(self)


class AnimationThread(QThread):
    """A thread to keep the animation timer independent of the main event loop.

    This prevents mouseovers and other events from causing animation lag. See
    QtDims.play() for public-facing docstring.
    """

    frame_requested = Signal(int, int)  # axis, point

    def __init__(self, parent: QObject | None = None) -> None:
        # FIXME there are attributes defined outside of __init__.
        super().__init__(parent=parent)
        self._interval = 1
        self._slider: ref[QtDimSliderWidget] = lambda: None
        self._waiter = threading.Event()
        self.current = 0
        self.step = 1

    def run(self):
        self.work()

    @property
    def slider(self) -> QtDimSliderWidget | None:
        """Return the slider for this animation thread."""
        return self._slider()

    def set_slider(self, slider):
        prev_slider = self.slider
        self._slider = ref(slider)
        self.set_fps(slider.fps)
        self.set_frame_range(slider.frame_range)
        if prev_slider is not None:
            prev_slider.fps_changed.disconnect(self.set_fps)
            prev_slider.range_changed.disconnect(self.set_frame_range)
            prev_slider.dims.events.current_step.disconnect(
                self._on_axis_changed
            )
            self.finished.disconnect(prev_slider.play_button._handle_stop)
            self.started.disconnect(prev_slider.play_button._handle_start)
        slider.fps_changed.connect(self.set_fps)
        slider.range_changed.connect(self.set_frame_range)
        slider.dims.events.current_step.connect(self._on_axis_changed)
        self.finished.connect(slider.play_button._handle_stop)
        self.started.connect(slider.play_button._handle_start)
        self.current = max(
            slider.dims.current_step[slider.axis], self.min_point
        )
        self.current = min(self.current, self.max_point)

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, value):
        self._interval = value

    @Slot()
    def work(self):
        """Play the animation."""
        # if loop_mode is once and we are already on the last frame,
        # return to the first frame... (so the user can keep hitting once)
        if self.loop_mode == LoopMode.ONCE:
            if self.step > 0 and self.current >= self.max_point - 1:
                self.frame_requested.emit(self.axis, self.min_point)
            elif self.step < 0 and self.current <= self.min_point + 1:
                self.frame_requested.emit(self.axis, self.max_point)
        else:
            # immediately advance one frame
            self.advance()
        self._waiter.clear()
        self._waiter.wait(self.interval / 1000)
        while not self._waiter.is_set():
            self.advance()
            self._waiter.wait(self.interval / 1000)

    def _stop(self):
        """Stop the animation."""
        self._waiter.set()

    @Slot(float)
    def set_fps(self, fps):
        """Set the frames per second value for the animation.

        Parameters
        ----------
        fps : float
            Frames per second for the animation.
        """
        if fps == 0:
            return self.finish()
        self.step = 1 if fps > 0 else -1  # negative fps plays in reverse
        self.interval = 1000 / abs(fps)
        return None

    @Slot(tuple)
    def set_frame_range(self, frame_range):
        """Frame range for animation, as (minimum_frame, maximum_frame).

        Parameters
        ----------
        frame_range : tuple(int, int)
            Frame range as tuple/list with range (minimum_frame, maximum_frame)
        """
        self.dimsrange = (0, self.dims.nsteps[self.axis], 1)

        if frame_range is not None:
            if frame_range[0] >= frame_range[1]:
                raise ValueError(
                    trans._('frame_range[0] must be <= frame_range[1]')
                )
            if frame_range[0] < self.dimsrange[0]:
                raise IndexError(trans._('frame_range[0] out of range'))
            if frame_range[1] * self.dimsrange[2] >= self.dimsrange[1]:
                raise IndexError(trans._('frame_range[1] out of range'))
        self.frame_range = frame_range

        if self.frame_range is not None:
            self.min_point, self.max_point = self.frame_range
        else:
            self.min_point = 0
            self.max_point = int(
                np.floor(self.dimsrange[1] - self.dimsrange[2])
            )
        self.max_point += 1  # range is inclusive

    @Slot()
    def advance(self):
        """Advance the current frame in the animation.

        Takes dims scale into account and restricts the animation to the
        requested frame_range, if entered.
        """
        self.current += self.step * self.dimsrange[2]
        if self.current < self.min_point:
            if (
                self.loop_mode == LoopMode.BACK_AND_FORTH
            ):  # 'loop_back_and_forth'
                self.step *= -1
                self.current = self.min_point + self.step * self.dimsrange[2]
            elif self.loop_mode == LoopMode.LOOP:  # 'loop'
                self.current = self.max_point + self.current - self.min_point
            else:  # loop_mode == 'once'
                return self.finish()
        elif self.current >= self.max_point:
            if (
                self.loop_mode == LoopMode.BACK_AND_FORTH
            ):  # 'loop_back_and_forth'
                self.step *= -1
                self.current = (
                    self.max_point + 2 * self.step * self.dimsrange[2]
                )
            elif self.loop_mode == LoopMode.LOOP:  # 'loop'
                self.current = self.min_point + self.current - self.max_point
            else:  # loop_mode == 'once'
                return self.finish()
        with self.dims.events.current_step.blocker(self._on_axis_changed):
            self.frame_requested.emit(self.axis, self.current)
        # self.timer.start()
        return None

    @property
    def loop_mode(self) -> LoopMode | None:
        """Loop mode for animation."""
        return getattr(self.slider, 'loop_mode', None)

    @property
    def axis(self) -> int | None:
        """Return the axis for this animation thread."""
        return getattr(self.slider, 'axis', None)

    @property
    def dims(self) -> Dims | None:
        """Return the dims for this animation thread."""
        return getattr(self.slider, 'dims', None)

    def finish(self):
        """Emit the finished event signal."""
        self._stop()

    def _on_axis_changed(self):
        """Update the current frame if the axis has changed."""
        # slot for external events to update the current frame
        if self.dims is not None:
            self.current = self.dims.current_step[self.axis]


class QMarginSlidersPopup(QMirroredSlidersPopup):
    def __init__(self, dims: Dims, axis: int, parent=None) -> None:
        super().__init__(parent)

        self.dims = ref(dims)
        self.axis = axis

        self._reset_sliders()

        self.left_slider.valueChanged.connect(self._update_margin_left)
        self.right_slider.valueChanged.connect(self._update_margin_right)
        dims.events.margin_left.connect(self._reset_sliders)
        dims.events.margin_right.connect(self._reset_sliders)

    def _update_margin_left(self, value):
        if (dims := self.dims()) is None:
            self.left_slider.valueChanged.disconnect(self._update_margin_left)
            return

        margin_left_step = list(dims.margin_left_step)
        margin_left_step[self.axis] = value
        dims.margin_left_step = tuple(margin_left_step)

    def _update_margin_right(self, value):
        if (dims := self.dims()) is None:
            self.right_slider.valueChanged.disconnect(
                self._update_margin_right
            )
            return

        margin_right_step = list(dims.margin_right_step)
        margin_right_step[self.axis] = value
        dims.margin_right_step = tuple(margin_right_step)

    def _reset_sliders(self):
        if (dims := self.dims()) is None:
            return

        with (
            qt_signals_blocked(self.left_slider),
            qt_signals_blocked(self.right_slider),
        ):
            self.left_slider.setRange(0, dims.nsteps[self.axis] - 1)
            self.left_slider.setValue(dims.margin_left_step[self.axis])
            self.right_slider.setRange(0, dims.nsteps[self.axis] - 1)
            self.right_slider.setValue(dims.margin_right_step[self.axis])

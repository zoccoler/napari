"""This module defines actions (functions) that operate on layers and its submenus.

Among other potential uses, these will populate the menu when you right-click
on a layer in the LayerList.

The Actions in LAYER_ACTIONS are registered with the application when it is
created in `_app_model._app`.  Modifying this list at runtime will have no
effect.  Use `app.register_action` to register new actions at runtime.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from app_model.types import Action, SubmenuItem

from napari._app_model.constants import MenuGroup, MenuId
from napari._app_model.context import LayerListSelectionContextKeys as LLSCK
from napari.layers import _layer_actions
from napari.utils.translations import trans

if TYPE_CHECKING:
    from app_model.types import MenuRuleDict

# Layer submenus
LAYERLIST_CONTEXT_SUBMENUS = [
    (
        MenuId.LAYERLIST_CONTEXT,
        SubmenuItem(
            submenu=MenuId.LAYERS_CONTEXT_CONVERT_DTYPE,
            title=trans._('Convert data type'),
            group=MenuGroup.LAYERLIST_CONTEXT.CONVERSION,
            order=None,
            enablement=LLSCK.all_selected_layers_labels,
        ),
    ),
    (
        MenuId.LAYERLIST_CONTEXT,
        SubmenuItem(
            submenu=MenuId.LAYERS_CONTEXT_PROJECT,
            title=trans._('Projections'),
            group=MenuGroup.LAYERLIST_CONTEXT.SPLIT_MERGE,
            order=None,
            enablement=LLSCK.active_layer_is_image_3d,
        ),
    ),
    (
        MenuId.LAYERLIST_CONTEXT,
        SubmenuItem(
            submenu=MenuId.LAYERS_CONTEXT_COPY_SPATIAL,
            title=trans._('Copy scale and transforms'),
            group=MenuGroup.LAYERLIST_CONTEXT.COPY_SPATIAL,
            order=None,
            enablement=(LLSCK.num_selected_layers == 1),
        ),
    ),
]

# The following dicts define groups to which menu items in the layer list context menu can belong
# see https://app-model.readthedocs.io/en/latest/types/#app_model.types.MenuRule for details
LAYERCTX_SPLITMERGE: MenuRuleDict = {
    'id': MenuId.LAYERLIST_CONTEXT,
    'group': MenuGroup.LAYERLIST_CONTEXT.SPLIT_MERGE,
}
LAYERCTX_CONVERSION: MenuRuleDict = {
    'id': MenuId.LAYERLIST_CONTEXT,
    'group': MenuGroup.LAYERLIST_CONTEXT.CONVERSION,
}
LAYERCTX_LINK: MenuRuleDict = {
    'id': MenuId.LAYERLIST_CONTEXT,
    'group': MenuGroup.LAYERLIST_CONTEXT.LINK,
}

# Statically defined Layer actions.
# modifying this list at runtime has no effect.
LAYERLIST_CONTEXT_ACTIONS: list[Action] = [
    Action(
        id='napari.layer.duplicate',
        title=trans._('Duplicate Layer'),
        callback=_layer_actions._duplicate_layer,
        menus=[LAYERCTX_SPLITMERGE],
    ),
    Action(
        id='napari.layer.split_stack',
        title=trans._('Split Stack'),
        callback=_layer_actions._split_stack,
        menus=[{**LAYERCTX_SPLITMERGE, 'when': ~LLSCK.active_layer_is_rgb}],
        enablement=LLSCK.active_layer_is_image_3d,
    ),
    Action(
        id='napari.layer.split_rgb',
        title=trans._('Split RGB'),
        callback=_layer_actions._split_rgb,
        menus=[{**LAYERCTX_SPLITMERGE, 'when': LLSCK.active_layer_is_rgb}],
        enablement=LLSCK.active_layer_is_rgb,
    ),
    Action(
        id='napari.layer.merge_rgb',
        title=trans._('Merge to RGB'),
        callback=partial(_layer_actions._merge_stack, rgb=True),
        enablement=(
            (
                (LLSCK.num_selected_layers == 3)
                | (LLSCK.num_selected_layers == 4)
            )
            & (LLSCK.num_selected_image_layers == LLSCK.num_selected_layers)
            & LLSCK.all_selected_layers_same_shape
        ),
        menus=[LAYERCTX_SPLITMERGE],
    ),
    Action(
        id='napari.layer.convert_to_labels',
        title=trans._('Convert to Labels'),
        callback=_layer_actions._convert_to_labels,
        enablement=(
            (
                (LLSCK.num_selected_image_layers >= 1)
                | (LLSCK.num_selected_shapes_layers >= 1)
            )
            & LLSCK.all_selected_layers_same_type
            & ~LLSCK.selected_empty_shapes_layer
        ),
        menus=[LAYERCTX_CONVERSION],
    ),
    Action(
        id='napari.layer.convert_to_image',
        title=trans._('Convert to Image'),
        callback=_layer_actions._convert_to_image,
        enablement=(
            (LLSCK.num_selected_labels_layers >= 1)
            & LLSCK.all_selected_layers_same_type
        ),
        menus=[LAYERCTX_CONVERSION],
    ),
    Action(
        id='napari.layer.merge_stack',
        title=trans._('Merge to Stack'),
        callback=_layer_actions._merge_stack,
        enablement=(
            (LLSCK.num_selected_layers > 1)
            & (LLSCK.num_selected_image_layers == LLSCK.num_selected_layers)
            & LLSCK.all_selected_layers_same_shape
        ),
        menus=[LAYERCTX_SPLITMERGE],
    ),
    Action(
        id='napari.layer.toggle_visibility',
        title=trans._('Toggle visibility'),
        callback=_layer_actions._toggle_visibility,
        menus=[
            {
                'id': MenuId.LAYERLIST_CONTEXT,
                'group': MenuGroup.NAVIGATION,
            }
        ],
    ),
    Action(
        id='napari.layer.link_selected_layers',
        title=trans._('Link Layers'),
        callback=_layer_actions._link_selected_layers,
        enablement=(
            (LLSCK.num_selected_layers > 1) & ~LLSCK.num_selected_layers_linked
        ),
        menus=[{**LAYERCTX_LINK, 'when': ~LLSCK.num_selected_layers_linked}],
    ),
    Action(
        id='napari.layer.unlink_selected_layers',
        title=trans._('Unlink Layers'),
        callback=_layer_actions._unlink_selected_layers,
        enablement=LLSCK.num_selected_layers_linked,
        menus=[{**LAYERCTX_LINK, 'when': LLSCK.num_selected_layers_linked}],
    ),
    Action(
        id='napari.layer.select_linked_layers',
        title=trans._('Select Linked Layers'),
        callback=_layer_actions._select_linked_layers,
        enablement=LLSCK.num_unselected_linked_layers,
        menus=[LAYERCTX_LINK],
    ),
    Action(
        id='napari.layer.show_selected',
        title=trans._('Show All Selected Layers'),
        callback=_layer_actions._show_selected,
        menus=[
            {
                'id': MenuId.LAYERLIST_CONTEXT,
                'group': MenuGroup.NAVIGATION,
            }
        ],
    ),
    Action(
        id='napari.layer.hide_selected',
        title=trans._('Hide All Selected Layers'),
        callback=_layer_actions._hide_selected,
        menus=[
            {
                'id': MenuId.LAYERLIST_CONTEXT,
                'group': MenuGroup.NAVIGATION,
            }
        ],
    ),
    Action(
        id='napari.layer.show_unselected',
        title=trans._('Show All Unselected Layers'),
        callback=_layer_actions._show_unselected,
        menus=[
            {
                'id': MenuId.LAYERLIST_CONTEXT,
                'group': MenuGroup.NAVIGATION,
            }
        ],
    ),
    Action(
        id='napari.layer.hide_unselected',
        title=trans._('Hide All Unselected Layers'),
        callback=_layer_actions._hide_unselected,
        menus=[
            {
                'id': MenuId.LAYERLIST_CONTEXT,
                'group': MenuGroup.NAVIGATION,
            }
        ],
    ),
]

for _dtype in (
    'int8',
    'int16',
    'int32',
    'int64',
    'uint8',
    'uint16',
    'uint32',
    'uint64',
):
    LAYERLIST_CONTEXT_ACTIONS.append(
        Action(
            id=f'napari.layer.convert_to_{_dtype}',
            title=trans._('Convert to {dtype}', dtype=_dtype),
            callback=partial(_layer_actions._convert_dtype, mode=_dtype),
            enablement=(
                LLSCK.all_selected_layers_labels
                & (LLSCK.active_layer_dtype != _dtype)
            ),
            menus=[{'id': MenuId.LAYERS_CONTEXT_CONVERT_DTYPE}],
        )
    )

for mode in ('max', 'min', 'std', 'sum', 'mean', 'median'):
    LAYERLIST_CONTEXT_ACTIONS.append(
        Action(
            id=f'napari.layer.project_{mode}',
            title=trans._('{mode} projection', mode=mode),
            callback=partial(_layer_actions._project, mode=mode),
            enablement=LLSCK.active_layer_is_image_3d,
            menus=[{'id': MenuId.LAYERS_CONTEXT_PROJECT}],
        )
    )

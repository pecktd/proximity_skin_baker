"""This module provides functionality to bake skin weights using a proximity wrap method in Maya."""

from dataclasses import dataclass
from typing import Union
from functools import partial
import time
from functools import wraps

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2

import maya.cmds as mc
import maya.mel as mm

NAMESPACE = "proximity_bake"


@dataclass
class Joint:
    name: str
    world_position: tuple[float, float, float]
    rotate: tuple[float, float, float]
    joint_orient: tuple[float, float, float]
    rotate_order: int
    radius: float
    parent_path: Union[str, None] = None


@dataclass
class Skin:
    """Represents skinning data, storing influence objects and their corresponding weights for use within this module."""

    influence_objects: list[str]
    weilghts: list[float]


def timer(func: callable):
    """
    A decorator that measures and prints the execution time of the wrapped function.

    The decorator calculates the elapsed time in hours, minutes, and seconds,
    and prints it in the format `HH:MM:SS.SS` after the wrapped function completes.
    It also ensures that the wrapped function's signature and behavior remain unchanged.

    Example:
        @timer
        def example_function():
            time.sleep(2)

        example_function()
        # Output: Elapsed time: 00:00:02.00
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        return_values = func(*args, **kwargs)
        end_time = time.time()
        hours, rem = divmod(end_time - start_time, 3600)
        minutes, seconds = divmod(rem, 60)

        print("Elapsed time: {:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))

        return return_values

    return wrapper


def get_joint_data(joint_path: str) -> Joint:
    """
    Retrieves joint attribute data for a given joint path.

    Args:
        joint_path (str): The full path to the joint in the Maya scene.

    Returns:
        Joint:
    """
    return Joint(
        name=joint_path.split("|")[-1],
        world_position=mc.xform(joint_path, q=True, ws=True, t=True),
        rotate=mc.getAttr(f"{joint_path}.r")[0],
        joint_orient=mc.getAttr(f"{joint_path}.jo")[0],
        rotate_order=mc.getAttr(f"{joint_path}.ro"),
        radius=mc.getAttr(f"{joint_path}.radi"),
    )


def build_path_from_root(path: str, root_path: str) -> str:
    """
    Builds a relative path from the root joint to a given joint.

    Args:
        path (str): The full path to the joint in the Maya scene.
        root_path (str): The full path to the root joint.

    Returns:
        str: The relative path from the root joint to the specified joint,
             starting with the root joint's name.
    """
    root = root_path.split("|")[-1]
    _, current_path = path.split(root_path)
    current_path = f"|{root}{current_path}"

    return current_path


def get_skeleton_data(root_joint_path: str) -> list[Joint]:
    """
    Retrieves data for a skeleton hierarchy starting from a root joint.

    This function collects information about the root joint and all its child joints
    in the hierarchy.

    Args:
        root_joint_path (str): The name of the root joint from which to begin traversal.

    Returns:
        list[Joint]:
    """
    root_joint_path = mc.ls(root_joint_path, l=True)[0]

    data: list[Joint] = [get_joint_data(root_joint_path)]

    child_joints: list[str] = sorted(
        mc.listRelatives(root_joint_path, ad=True, type="joint", f=True)
    )
    for joint_path in child_joints:
        current_data = get_joint_data(joint_path)

        current_path = build_path_from_root(joint_path, root_joint_path)
        parent_path = "|".join(current_path.split("|")[:-1])

        current_data.parent_path = parent_path

        data.append(current_data)

    return data


def add_namespace_to_full_path(namespace: str, full_path_name: str) -> str:
    """
    Adds a namespace to each node in a full Maya path.

    Args:
        namespace (str): The namespace to prepend to each node name.
        full_path_name (str): The full path name (e.g., '|root|joint1|joint2').

    Returns:
        str: The full path with the namespace added to each node (e.g., '|namespace:root|namespace:joint1|namespace:joint2').
    """
    if namespace:
        namespace = f"{namespace}:"

    return "|".join([f"{namespace}{n}" for n in full_path_name.split("|")[1:]])


def build_skeleton(data: list[Joint], namespace: str):
    """
    Creates a skeleton hierarchy in the Maya scene using the provided joint data.

    Args:
        data (list[Joint]): List of Joint dataclass instances containing joint attributes and hierarchy.
        namespace (str): Namespace to prepend to each joint name.

    The function creates joints, sets their attributes, and parents them according to the hierarchy.
    """
    for joint in data:

        joint_name = mc.createNode("joint", n=f"{namespace}:{joint.name}")

        mc.xform(joint_name, ws=True, t=joint.world_position)

        if joint.parent_path is not None:
            mc.parent(joint_name, add_namespace_to_full_path(namespace, joint.parent_path))

        mc.setAttr(f"{joint_name}.r", *joint.rotate)
        mc.setAttr(f"{joint_name}.jo", *joint.joint_orient)
        mc.setAttr(f"{joint_name}.ro", joint.rotate_order)
        mc.setAttr(f"{joint_name}.radi", joint.radius)


def get_related_skin_node(geom: str) -> str:
    """
    Retrieves the skinCluster node associated with a given geometry.

    Args:
        geom (str): The full path to the geometry in the Maya scene.

    Returns: str or bool
        The name of the skinCluster node if found, otherwise False.
    """
    history_nodes = mc.listHistory(geom)

    if not history_nodes:
        return False

    for node in history_nodes:
        if mc.nodeType(node) == "skinCluster":
            return node


def get_skin_data(skin_node: str, geom: str) -> Skin:
    """
    Retrieves skin data from a skinCluster node and the associated geometry.

    Args:
        skin_node (str): The name of the skinCluster node.
        geom (str): The full path to the geometry in the Maya scene.

    Returns:
        Skin: A dataclass containing the influence objects and their weights.
    """
    sel_list: om2.MSelectionList = om2.MSelectionList()
    sel_list.add(skin_node)
    sel_list.add(geom)

    mobj: om2.MObject = sel_list.getDependNode(0)
    mfnskin = oma2.MFnSkinCluster(mobj)

    geom: om2.MDagPath = sel_list.getDagPath(1)

    infs: list[om2.MDagPath] = mfnskin.influenceObjects()
    influence_objects = [inf.fullPathName() for inf in infs]

    sel_compos: om2.MSelectionList = om2.MGlobal.getSelectionListByName(
        f"{geom.fullPathName()}.vtx[*]"
    )
    compos = sel_compos.getComponent(0)[1]

    weights, _ = mfnskin.getWeights(geom, compos)
    weights = list(weights)

    return Skin(influence_objects=influence_objects, weilghts=weights)


def set_skin(skin_data: Skin, skin_node: str):
    """
    Sets the skin weights for a given skinCluster node based on the provided skin data.

    Args:
        skin_data (Skin): A dataclass containing the influence objects and their weights.
        skin_node (str): The name of the skinCluster node to set the weights on.
    """
    sel_list: om2.MSelectionList = om2.MSelectionList()
    sel_list.add(skin_node)

    skin_obj = sel_list.getDependNode(0)
    mfn_skin = oma2.MFnSkinCluster(skin_obj)

    geom = mfn_skin.getOutputGeometry()
    geom: om2.MDagPath = om2.MDagPath.getAPathTo(geom[0])

    sel_compos: om2.MSelectionList = om2.MGlobal.getSelectionListByName(
        f"{geom.fullPathName()}.vtx[*]"
    )
    compos: om2.MObject = sel_compos.getComponent(0)[1]

    inf_indices: om2.MDoubleArray = om2.MIntArray()
    for i in range(len(skin_data.influence_objects)):
        inf_indices.append(i)

    weights: om2.MDoubleArray = om2.MDoubleArray()
    for weight in skin_data.weilghts:
        weights.append(weight)

    mfn_skin.setWeights(geom, compos, inf_indices, weights, False)


def rebind_skin(skin_data: Skin, geom: str, namespace: str, root_joint_path: str):
    """
    Rebinds the skinCluster to a new geometry with the provided skin data.

    Args:
        skin_data (Skin): A dataclass containing the influence objects and their weights.
        geom (str): The full path to the geometry in the Maya scene.
        namespace (str): Namespace to prepend to each influence object name.
        root_joint_path (str): The full path to the root joint in the Maya scene.
    """

    influence_objects: list[str] = []
    for influence_path in skin_data.influence_objects:
        current_path = build_path_from_root(influence_path, root_joint_path)
        current_path = add_namespace_to_full_path(namespace, current_path)
        influence_objects.append(current_path)

    skin_node = mc.skinCluster(influence_objects + [geom], tsb=True)[0]
    set_skin(skin_data, skin_node)


def dup_and_clean_geom(geom_path: str, namespace: str) -> str:
    """
    Duplicates a geometry and cleans up its shapes by removing intermediate objects.

    Args:
        geom_path (str): The full path to the geometry in the Maya scene.
        namespace (str): Namespace to prepend to the duplicated geometry's name.

    Returns:
        str: The name of the duplicated geometry.
    """
    dupped_geom = mc.duplicate(geom_path, rr=True)[0]

    new_name = f"{namespace}:{geom_path.split('|')[-1]}"
    dupped_geom = mc.rename(dupped_geom, new_name)

    if mc.listRelatives(dupped_geom, p=True):
        mc.parent(dupped_geom, w=True)

    shapes = mc.listRelatives(dupped_geom, s=True)
    if not shapes:
        return dupped_geom

    for shape in shapes:
        if mc.getAttr(f"{shape}.intermediateObject"):
            mc.delete(shape)

    return dupped_geom


def cleanup():

    deleted_nodes: list[str] = []
    node: str
    for node in mc.ls():
        if node.startswith(f"{NAMESPACE}:"):
            deleted_nodes.append(node)

    mc.delete(deleted_nodes)

    all_namespaces: list[str] = mc.namespaceInfo(lon=True, r=True)
    namespaces = sorted(
        [n for n in all_namespaces if n.startswith(f"{NAMESPACE}:")],
        key=len,
        reverse=True,
    )
    for namespace in namespaces:
        mc.namespace(rm=namespace)


class SkinBaker(object):

    def __init__(self):

        self.ui = "skinBaker"
        self.win = f"{self.ui}Win"

        if mc.window(self.win, exists=True):
            mc.deleteUI(self.win)

        mc.window(self.win, t=self.ui)
        self.main_col = mc.columnLayout(adj=True)

        self.source_geom_tfbg = mc.textFieldButtonGrp(
            l="Source", ed=False, cw=[1, 60], adj=2, bl="Get", bc=partial(self._get_source_geom)
        )

        self.root_tfbg = mc.textFieldButtonGrp(
            l="Root Joint", ed=False, cw=[1, 60], adj=2, bl="Get", bc=partial(self._get_root_joint)
        )

        self.target_geom_tfbg = mc.textFieldButtonGrp(
            l="Target", ed=False, cw=[1, 60], adj=2, bl="Get", bc=partial(self._get_target_geom)
        )

        mc.separator()

        self.build_but = mc.button(l="Build", c=partial(self._build), h=50)

        mc.separator()

        self.influence_ifg = mc.intFieldGrp(e=False, l="Influence", cw=[1, 60], adj=2, nf=1, v1=10)

        mc.separator()

        self.bake_but = mc.button(l="Bake", c=partial(self._bake), h=50)

        mc.showWindow(self.win)
        mc.window(self.win, e=True, w=100, h=190)

    def _get_source_geom(self, *_):
        selection = mc.ls(sl=True, l=True)[0]
        mc.textFieldButtonGrp(self.source_geom_tfbg, e=True, tx=selection)

    def _get_root_joint(self, *_):
        selection = mc.ls(sl=True, l=True)[0]
        mc.textFieldButtonGrp(self.root_tfbg, e=True, tx=selection)

    def _get_target_geom(self, *_):
        selection = mc.ls(sl=True, l=True)[0]
        mc.textFieldButtonGrp(self.target_geom_tfbg, e=True, tx=selection)

    def _build(self, *_):
        """
        Builds the skeleton and sets up the skinning for the source and target geometries.
        """
        source_geom = mc.textFieldButtonGrp(self.source_geom_tfbg, q=True, tx=True)
        root_joint = mc.textFieldButtonGrp(self.root_tfbg, q=True, tx=True)
        target_geom = mc.textFieldButtonGrp(self.target_geom_tfbg, q=True, tx=True)

        source_skin_node = get_related_skin_node(source_geom)
        skeleton = get_skeleton_data(root_joint)
        skin_data = get_skin_data(source_skin_node, source_geom)

        build_skeleton(skeleton, NAMESPACE)
        dupped_source = dup_and_clean_geom(source_geom, NAMESPACE)
        rebind_skin(skin_data, dupped_source, NAMESPACE, root_joint)

        dupped_target = dup_and_clean_geom(target_geom, NAMESPACE)

        mc.select(dupped_target, r=True)
        wrap_node = mc.proximityWrap()[0]
        mc.proximityWrap(wrap_node, edit=True, addDrivers=[dupped_source])

        mc.namespace(set=":")

    @timer
    def _bake(self, *_):
        """
        Bakes the skin weights from the source geometry to the target geometry.
        """
        root: str = mc.textFieldButtonGrp(self.root_tfbg, q=True, tx=True)
        target: str = mc.textFieldButtonGrp(self.target_geom_tfbg, q=True, tx=True)

        source_root = f"{NAMESPACE}:{root.split('|')[-1]}"
        source_geom = f"{NAMESPACE}:{target.split('|')[-1]}"

        influence_number = mc.intFieldGrp(self.influence_ifg, q=True, v1=True)

        skin_node = get_related_skin_node(target)
        if skin_node:
            mc.skinCluster(skin_node, e=True, ub=True)

        mc.bakeDeformer(
            sm=source_geom,
            ss=source_root,
            dm=target,
            ds=source_root,
            mi=influence_number,
        )

        skin_node = get_related_skin_node(target)
        skin_data = get_skin_data(skin_node, target)

        mc.skinCluster(skin_node, e=True, ub=True)

        influence_objects: list[str] = []
        for inf in skin_data.influence_objects:
            parts = [":".join(p.split(":")[1:]) for p in inf.split("|") if p]
            influence_objects.append(f"*|{'|'.join(parts)}")

        skin_data.influence_objects = influence_objects

        skin_node = mc.skinCluster(skin_data.influence_objects + [target], tsb=True)[0]
        set_skin(skin_data, skin_node)

        cleanup()


def ui():
    app = SkinBaker()
    return app

"""
scanner.py — Maya Scene Doctor AI
Collects scene data from the current Maya session via maya.cmds.
Returns a structured dict ready to be serialized and sent to the AI backend.

Built by Ezz El-Din | LinkedIn: https://www.linkedin.com/in/ezzel-din-tarek-mostafa
"""

import maya.cmds as cmds
import maya.mel as mel
import os
import json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(fn, *args, **kwargs):
    """Run a cmds call and return None instead of raising on failure."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _attr(node, attr):
    """Read a single attribute value safely."""
    plug = "{}.{}".format(node, attr)
    try:
        return cmds.getAttr(plug)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Individual scan sections
# ---------------------------------------------------------------------------

def scan_scene_info():
    """Basic scene-level metadata."""
    scene_path = cmds.file(q=True, sceneName=True) or "untitled"
    scene_name = os.path.basename(scene_path)

    # Frame range
    start = cmds.playbackOptions(q=True, minTime=True)
    end   = cmds.playbackOptions(q=True, maxTime=True)
    fps_str = cmds.currentUnit(q=True, time=True)   # e.g. "film", "ntsc", "pal"

    # Up-axis
    up_axis = cmds.upAxis(q=True, axis=True)

    # Linear / angular units
    linear_unit  = cmds.currentUnit(q=True, linear=True)
    angular_unit = cmds.currentUnit(q=True, angle=True)

    return {
        "scene_path":    scene_path,
        "scene_name":    scene_name,
        "frame_range":   {"start": start, "end": end},
        "fps":           fps_str,
        "up_axis":       up_axis,
        "linear_unit":   linear_unit,
        "angular_unit":  angular_unit,
    }


def scan_node_counts():
    """Count nodes by type — quick health overview."""
    all_nodes = cmds.ls(long=True) or []

    type_counts = {}
    for node in all_nodes:
        node_type = cmds.nodeType(node)
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    # Summarise the most common types (top-15) to keep payload small
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    top_types = dict(sorted_types[:15])

    return {
        "total_nodes":   len(all_nodes),
        "top_node_types": top_types,
    }


def scan_meshes():
    """Per-mesh geometry statistics and common issues."""
    meshes = cmds.ls(type="mesh", long=True) or []
    mesh_data = []

    for mesh in meshes:
        # Skip intermediate objects
        if cmds.getAttr("{}.intermediateObject".format(mesh)):
            continue

        transform = (cmds.listRelatives(mesh, parent=True, fullPath=True) or [None])[0]

        vert_count  = cmds.polyEvaluate(mesh, vertex=True)   or 0
        face_count  = cmds.polyEvaluate(mesh, face=True)     or 0
        edge_count  = cmds.polyEvaluate(mesh, edge=True)     or 0
        uv_count    = cmds.polyEvaluate(mesh, uvcoord=True)  or 0
        tri_count   = cmds.polyEvaluate(mesh, triangle=True) or 0

        # UV sets
        uv_sets = cmds.polyUVSet(mesh, q=True, allUVSets=True) or []

        # Non-manifold geometry
        non_manifold_verts = _safe_get(cmds.polyInfo, mesh, nonManifoldVertices=True) or []
        non_manifold_edges = _safe_get(cmds.polyInfo, mesh, nonManifoldEdges=True)    or []

        # Lamina faces
        lamina_faces = _safe_get(cmds.polyInfo, mesh, laminaFaces=True) or []

        # History nodes connected upstream
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        history_count = len(history)

        # Freeze transforms check
        transform_frozen = False
        if transform:
            tx = _attr(transform, "translateX") or 0
            ty = _attr(transform, "translateY") or 0
            tz = _attr(transform, "translateZ") or 0
            rx = _attr(transform, "rotateX")    or 0
            ry = _attr(transform, "rotateY")    or 0
            rz = _attr(transform, "rotateZ")    or 0
            sx = _attr(transform, "scaleX")     or 1
            sy = _attr(transform, "scaleY")     or 1
            sz = _attr(transform, "scaleZ")     or 1
            transform_frozen = (
                tx == 0 and ty == 0 and tz == 0 and
                rx == 0 and ry == 0 and rz == 0 and
                sx == 1 and sy == 1 and sz == 1
            )

        mesh_data.append({
            "transform":           transform,
            "shape":               mesh,
            "vertices":            vert_count,
            "faces":               face_count,
            "edges":               edge_count,
            "uvs":                 uv_count,
            "triangles":           tri_count,
            "uv_sets":             uv_sets,
            "non_manifold_verts":  len(non_manifold_verts),
            "non_manifold_edges":  len(non_manifold_edges),
            "lamina_faces":        len(lamina_faces),
            "construction_history_nodes": history_count,
            "transforms_frozen":   transform_frozen,
        })

    return mesh_data


def scan_materials():
    """Shading engines, unassigned materials, missing textures."""
    shading_engines = cmds.ls(type="shadingEngine") or []
    materials_data  = []
    missing_textures = []

    for sg in shading_engines:
        # Skip Maya default shading groups
        if sg in ("initialShadingGroup", "initialParticleSE"):
            continue

        # Connected surface shader
        shader_plug = "{}.surfaceShader".format(sg)
        shader_connections = cmds.listConnections(shader_plug, source=True) or []
        shader = shader_connections[0] if shader_connections else None
        shader_type = cmds.nodeType(shader) if shader else "unknown"

        # Members (assigned faces/objects)
        members = cmds.sets(sg, q=True) or []

        # Collect file texture nodes in this shader's network
        texture_files = []
        if shader:
            file_nodes = cmds.listHistory(shader, type="file") or []
            for fn in file_nodes:
                path = _attr(fn, "fileTextureName") or ""
                exists = os.path.isfile(path) if path else False
                texture_files.append({"node": fn, "path": path, "exists": exists})
                if path and not exists:
                    missing_textures.append({"node": fn, "path": path})

        materials_data.append({
            "shading_engine": sg,
            "shader":         shader,
            "shader_type":    shader_type,
            "assigned_to":    len(members),
            "texture_files":  texture_files,
        })

    return {
        "shading_groups":   materials_data,
        "missing_textures": missing_textures,
    }


def scan_joints_and_rigs():
    """Joint hierarchy, bind poses, skin clusters."""
    joints = cmds.ls(type="joint", long=True) or []

    root_joints = []
    for j in joints:
        parent = cmds.listRelatives(j, parent=True, type="joint", fullPath=True)
        if not parent:
            root_joints.append(j)

    # Skin clusters
    skin_clusters = cmds.ls(type="skinCluster") or []
    skin_data = []

    for sc in skin_clusters:
        # Geometry driven by this skin cluster
        geo = cmds.skinCluster(sc, q=True, geometry=True) or []
        # Influences (joints)
        influences = cmds.skinCluster(sc, q=True, influence=True) or []

        # Max influences per vertex
        max_inf = _attr(sc, "maxInfluences") or 0

        skin_data.append({
            "skin_cluster":    sc,
            "geometry":        geo,
            "influence_count": len(influences),
            "max_influences":  max_inf,
        })

    # Check for joints with non-zero jointOrient having children with locked attrs
    locked_joint_issues = []
    for j in joints:
        locked = []
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            if cmds.getAttr("{}.{}".format(j, attr), lock=True):
                locked.append(attr)
        if locked:
            locked_joint_issues.append({"joint": j, "locked_attrs": locked})

    return {
        "total_joints":       len(joints),
        "root_joints":        root_joints,
        "skin_clusters":      skin_data,
        "locked_joint_attrs": locked_joint_issues,
    }


def scan_namespaces():
    """List non-default namespaces — leftover references are a common issue."""
    all_ns = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
    # Filter out Maya built-in namespaces
    built_ins = {"UI", "shared"}
    custom_ns = [ns for ns in all_ns if ns not in built_ins]
    return {"custom_namespaces": custom_ns, "count": len(custom_ns)}


def scan_references():
    """Loaded / unloaded references in the scene."""
    ref_nodes = cmds.ls(references=True) or []
    refs = []

    for ref in ref_nodes:
        try:
            file_path = cmds.referenceQuery(ref, filename=True)
        except Exception:
            file_path = "unknown"
        try:
            loaded = cmds.referenceQuery(ref, isLoaded=True)
        except Exception:
            loaded = False
        exists = os.path.isfile(file_path) if file_path != "unknown" else False

        refs.append({
            "ref_node":  ref,
            "file_path": file_path,
            "loaded":    loaded,
            "file_exists": exists,
        })

    return {"references": refs, "count": len(refs)}


def scan_unknown_nodes():
    """Unknown nodes usually mean missing plugins."""
    unknown = cmds.ls(type="unknown") or []
    unknown_dg = cmds.ls(type="unknownDag") or []
    all_unknown = unknown + unknown_dg

    details = []
    for node in all_unknown:
        unknown_type = _attr(node, "unknownNodeType") or "n/a"
        details.append({"node": node, "unknown_type": unknown_type})

    return {"unknown_nodes": details, "count": len(all_unknown)}


def scan_display_layers():
    """Display layers and their members."""
    layers = cmds.ls(type="displayLayer") or []
    layer_data = []

    for layer in layers:
        if layer == "defaultLayer":
            continue
        members = cmds.editDisplayLayerMembers(layer, q=True, fullNames=True) or []
        visible  = _attr(layer, "visibility")
        layer_data.append({
            "layer":    layer,
            "visible":  visible,
            "members":  len(members),
        })

    return {"display_layers": layer_data}


def scan_animation():
    """Anim curves, baked keys, infinite extrapolation issues."""
    anim_curves = cmds.ls(type="animCurve") or []

    # Check for curves with pre/post infinity set to 'constant' vs 'cycle' etc.
    infinity_issues = []
    for ac in anim_curves:
        pre  = _safe_get(cmds.setInfinity, ac, q=True, preInfinite=True)
        post = _safe_get(cmds.setInfinity, ac, q=True, postInfinite=True)
        if pre and post:
            pre  = pre[0]  if isinstance(pre,  list) else pre
            post = post[0] if isinstance(post, list) else post
            if pre != "constant" or post != "constant":
                infinity_issues.append({
                    "curve":        ac,
                    "pre_infinity":  pre,
                    "post_infinity": post,
                })

    return {
        "total_anim_curves":   len(anim_curves),
        "infinity_issues":     infinity_issues,
        "infinity_issue_count": len(infinity_issues),
    }


def scan_lights():
    """Scene lights — type, intensity, color, position, visibility, and common issues."""
    light_types = [
        # Maya native
        "ambientLight", "directionalLight", "pointLight",
        "spotLight", "areaLight", "volumeLight",
        # Arnold
        "aiAreaLight", "aiSkyDomeLight", "aiPhotometricLight",
        "aiMeshLight", "aiLightPortal",
        # V-Ray
        "VRayLightSphereShape", "VRayLightDomeShape",
        "VRayLightRectShape", "VRaySunShape",
        # Redshift
        "RedshiftPhysicalLight", "RedshiftDomeLight",
        "RedshiftIESLight", "RedshiftPortalLight",
        # Karma / USD
        "karmaLightFilter", "UsdLuxSphereLight",
        "UsdLuxDiskLight", "UsdLuxRectLight",
    ]

    all_lights = []
    for lt in light_types:
        found = cmds.ls(type=lt, long=True) or []
        all_lights.extend(found)

    light_data = []
    issues = []

    for light in all_lights:
        transform = (cmds.listRelatives(light, parent=True, fullPath=True) or [None])[0]
        light_type = cmds.nodeType(light)
        intensity  = _attr(light, "intensity")
        color_raw  = _attr(light, "color")
        visible    = _attr(light, "visibility")

        # Normalise color — getAttr returns [(r, g, b)] for color attrs
        if isinstance(color_raw, list) and color_raw:
            color = list(color_raw[0]) if isinstance(color_raw[0], (list, tuple)) else color_raw
        else:
            color = None

        # Position and rotation from parent transform
        position = None
        rotation = None
        if transform:
            tx = _attr(transform, "translateX") or 0
            ty = _attr(transform, "translateY") or 0
            tz = _attr(transform, "translateZ") or 0
            position = [tx, ty, tz]
            rx = _attr(transform, "rotateX") or 0
            ry = _attr(transform, "rotateY") or 0
            rz = _attr(transform, "rotateZ") or 0
            rotation = [rx, ry, rz]

        # Check parent transform visibility too
        if visible and transform:
            t_vis = _attr(transform, "visibility")
            if t_vis is not None:
                visible = t_vis

        # Detect issues
        light_issues = []
        if intensity is not None and intensity == 0:
            light_issues.append("intensity is 0")
            issues.append({"light": transform or light, "issue": "intensity is 0"})
        if intensity is not None and intensity < 0:
            light_issues.append("negative intensity ({})".format(intensity))
            issues.append({"light": transform or light, "issue": "negative intensity ({})".format(intensity)})
        if not visible:
            light_issues.append("light is hidden")
            issues.append({"light": transform or light, "issue": "light is hidden"})
        if color and all(c == 0 for c in color[:3]):
            light_issues.append("black color (produces no light)")
            issues.append({"light": transform or light, "issue": "black color (produces no light)"})
        if intensity is not None and intensity > 10000:
            light_issues.append("overexposure risk (intensity {})".format(intensity))
            issues.append({"light": transform or light, "issue": "overexposure risk (intensity {})".format(intensity)})

        light_data.append({
            "transform": transform,
            "shape":     light,
            "type":      light_type,
            "intensity": intensity,
            "color":     color,
            "position":  position,
            "rotation":  rotation,
            "visible":   visible,
            "issues":    light_issues,
        })

    return {
        "lights":      light_data,
        "total":       len(light_data),
        "issue_count": len(issues),
        "issues":      issues,
    }


def scan_render_settings():
    """Active renderer and basic render settings."""
    try:
        renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer") or "unknown"
    except Exception:
        renderer = "unknown"

    try:
        width  = cmds.getAttr("defaultResolution.width")
        height = cmds.getAttr("defaultResolution.height")
    except Exception:
        width, height = None, None

    try:
        start_frame = cmds.getAttr("defaultRenderGlobals.startFrame")
        end_frame   = cmds.getAttr("defaultRenderGlobals.endFrame")
    except Exception:
        start_frame, end_frame = None, None

    return {
        "renderer":    renderer,
        "resolution":  {"width": width, "height": height},
        "render_range": {"start": start_frame, "end": end_frame},
    }


def scan_cameras():
    """All cameras except Maya defaults — focal length, clipping, renderable flag."""
    default_cameras = {"persp", "top", "front", "side"}
    all_cam_shapes = cmds.ls(type="camera", long=True) or []

    camera_data = []
    issues = []
    has_renderable = False

    for cam in all_cam_shapes:
        transform = (cmds.listRelatives(cam, parent=True, fullPath=True) or [None])[0]
        short_name = transform.split("|")[-1] if transform else cam.split("|")[-1]

        # Skip Maya default cameras
        if short_name in default_cameras:
            continue

        focal_length = _attr(cam, "focalLength")
        near_clip    = _attr(cam, "nearClipPlane")
        far_clip     = _attr(cam, "farClipPlane")
        renderable   = _attr(cam, "renderable")

        if renderable:
            has_renderable = True

        # Detect issues
        cam_issues = []
        if near_clip is not None and near_clip < 0.01:
            cam_issues.append("near clip too small ({})".format(near_clip))
            issues.append({"camera": short_name, "issue": "near clip too small ({})".format(near_clip)})
        if far_clip is not None and far_clip > 1000000:
            cam_issues.append("far clip too large ({})".format(far_clip))
            issues.append({"camera": short_name, "issue": "far clip too large ({})".format(far_clip)})
        if near_clip is not None and far_clip is not None and far_clip > 0 and near_clip > 0:
            ratio = far_clip / near_clip
            if ratio > 100000:
                cam_issues.append("extreme clip ratio ({:.0f}x — may cause z-fighting)".format(ratio))
                issues.append({"camera": short_name, "issue": "extreme clip ratio ({:.0f}x)".format(ratio)})

        camera_data.append({
            "transform":    transform,
            "shape":        cam,
            "name":         short_name,
            "focal_length": focal_length,
            "near_clip":    near_clip,
            "far_clip":     far_clip,
            "renderable":   renderable,
            "issues":       cam_issues,
        })

    # Global issue: no renderable camera found among custom cameras
    if camera_data and not has_renderable:
        issues.append({"camera": "(scene)", "issue": "no renderable camera found"})

    return {
        "cameras":     camera_data,
        "total":       len(camera_data),
        "issue_count": len(issues),
        "issues":      issues,
    }


def scan_render_layers():
    """Render layers — name, enabled state, member count."""
    layers = cmds.ls(type="renderLayer") or []
    layer_data = []
    issues = []
    enabled_count = 0

    for layer in layers:
        # Skip the default render layer
        if layer == "defaultRenderLayer":
            continue

        renderable = _attr(layer, "renderable")
        members = _safe_get(cmds.editRenderLayerMembers, layer, q=True, fullNames=True) or []
        member_count = len(members)

        if renderable:
            enabled_count += 1

        # Detect issues
        layer_issues = []
        if member_count == 0:
            layer_issues.append("empty render layer")
            issues.append({"layer": layer, "issue": "empty render layer"})

        layer_data.append({
            "layer":        layer,
            "renderable":   renderable,
            "member_count": member_count,
            "issues":       layer_issues,
        })

    # Global issue: all custom layers disabled
    if layer_data and enabled_count == 0:
        issues.append({"layer": "(all)", "issue": "all render layers are disabled"})

    return {
        "render_layers": layer_data,
        "total":         len(layer_data),
        "issue_count":   len(issues),
        "issues":        issues,
    }


# ---------------------------------------------------------------------------
# Master scan function
# ---------------------------------------------------------------------------

def run_scan():
    """
    Run all scan sections and return a unified dict.
    This is the only function called by main.py.

    Returns:
        dict: Full scene report ready for JSON serialisation.
    """
    print("[Scene Doctor] Starting scene scan...")

    report = {
        "scene_info":      scan_scene_info(),
        "node_counts":     scan_node_counts(),
        "meshes":          scan_meshes(),
        "materials":       scan_materials(),
        "joints_and_rigs": scan_joints_and_rigs(),
        "namespaces":      scan_namespaces(),
        "references":      scan_references(),
        "unknown_nodes":   scan_unknown_nodes(),
        "lights":          scan_lights(),
        "cameras":         scan_cameras(),
        "render_layers":   scan_render_layers(),
        "display_layers":  scan_display_layers(),
        "animation":       scan_animation(),
        "render_settings": scan_render_settings(),
    }

    print("[Scene Doctor] Scan complete. {} mesh(es), {} light(s), {} camera(s), {} unknown node(s), {} missing texture(s).".format(
        len(report["meshes"]),
        report["lights"]["total"],
        report["cameras"]["total"],
        report["unknown_nodes"]["count"],
        len(report["materials"]["missing_textures"]),
    ))

    return report


def scan_to_prompt(report=None):
    """
    Convert the scan report into a clean AI prompt string.
    Call run_scan() automatically if no report is passed.

    Args:
        report (dict, optional): Pre-computed report from run_scan().

    Returns:
        str: Ready-to-send prompt for the AI backend.
    """
    if report is None:
        report = run_scan()

    scene = report["scene_info"]
    nodes = report["node_counts"]
    meshes = report["meshes"]
    mats = report["materials"]
    lights = report["lights"]
    cameras = report["cameras"]
    rlayers = report["render_layers"]
    rigs = report["joints_and_rigs"]
    refs = report["references"]
    unknown = report["unknown_nodes"]
    anim = report["animation"]

    # Build a human-readable summary to keep token usage reasonable
    lines = [
        "## Maya Scene Diagnostic Report",
        "",
        "**Scene:** `{}`".format(scene["scene_name"]),
        "**Frame Range:** {} – {}  |  **FPS:** {}  |  **Up Axis:** {}".format(
            scene["frame_range"]["start"], scene["frame_range"]["end"],
            scene["fps"], scene["up_axis"]
        ),
        "",
        "### Node Overview",
        "- Total nodes: {}".format(nodes["total_nodes"]),
        "- Top types: {}".format(
            ", ".join("{} ({})".format(k, v) for k, v in nodes["top_node_types"].items())
        ),
        "",
        "### Meshes ({} mesh shapes)".format(len(meshes)),
    ]

    for m in meshes:
        flags = []
        if m["non_manifold_verts"] > 0:
            flags.append("non-manifold verts: {}".format(m["non_manifold_verts"]))
        if m["non_manifold_edges"] > 0:
            flags.append("non-manifold edges: {}".format(m["non_manifold_edges"]))
        if m["lamina_faces"] > 0:
            flags.append("lamina faces: {}".format(m["lamina_faces"]))
        if not m["transforms_frozen"]:
            flags.append("transforms NOT frozen")
        if m["construction_history_nodes"] > 3:
            flags.append("high history ({} nodes)".format(m["construction_history_nodes"]))

        flag_str = "  ⚠ " + " | ".join(flags) if flags else "  ✓ clean"
        lines.append("- `{}` — {} verts, {} faces, {} tris{}".format(
            m["transform"], m["vertices"], m["faces"], m["triangles"], flag_str
        ))

    lines += [
        "",
        "### Materials",
        "- Shading groups: {}".format(len(mats["shading_groups"])),
        "- Missing textures: {}".format(len(mats["missing_textures"])),
    ]
    for mt in mats["missing_textures"]:
        lines.append("  - `{}` → `{}`".format(mt["node"], mt["path"]))

    lines += [
        "",
        "### Lights ({} lights)".format(lights["total"]),
        "- Total lights: {}".format(lights["total"]),
        "- Issues found: {}".format(lights["issue_count"]),
    ]
    for lt in lights["lights"]:
        issue_str = ""
        if lt["issues"]:
            issue_str = "  ⚠ " + " | ".join(lt["issues"])
        else:
            issue_str = "  ✓ ok"
        lines.append("- `{}` — type: {} | intensity: {} | visible: {}{}".format(
            lt["transform"], lt["type"], lt["intensity"], lt["visible"], issue_str
        ))
    for li in lights["issues"]:
        lines.append("  - ⚠ {} → {}".format(li["light"], li["issue"]))

    lines += [
        "",
        "### Cameras ({} custom)".format(cameras["total"]),
    ]
    if cameras["total"] == 0:
        lines.append("- No custom cameras found (only Maya defaults)")
    for cam in cameras["cameras"]:
        renderable_str = "renderable" if cam["renderable"] else "NOT renderable"
        issue_str = ""
        if cam["issues"]:
            issue_str = "  ⚠ " + " | ".join(cam["issues"])
        else:
            issue_str = "  ✓ ok"
        lines.append("- `{}` — focal: {} | near: {} | far: {} | {}{}".format(
            cam["name"], cam["focal_length"], cam["near_clip"],
            cam["far_clip"], renderable_str, issue_str
        ))
    for ci in cameras["issues"]:
        lines.append("  - ⚠ {} → {}".format(ci["camera"], ci["issue"]))

    lines += [
        "",
        "### Render Layers ({} layers)".format(rlayers["total"]),
    ]
    if rlayers["total"] == 0:
        lines.append("- No custom render layers")
    for rl in rlayers["render_layers"]:
        status = "enabled" if rl["renderable"] else "DISABLED"
        issue_str = ""
        if rl["issues"]:
            issue_str = "  ⚠ " + " | ".join(rl["issues"])
        lines.append("- `{}` — {} | members: {}{}".format(
            rl["layer"], status, rl["member_count"], issue_str
        ))
    for rli in rlayers["issues"]:
        lines.append("  - ⚠ {} → {}".format(rli["layer"], rli["issue"]))

    lines += [
        "",
        "### Rigs & Joints",
        "- Total joints: {}".format(rigs["total_joints"]),
        "- Root joints: {}".format(len(rigs["root_joints"])),
        "- Skin clusters: {}".format(len(rigs["skin_clusters"])),
        "- Joints with locked attrs: {}".format(len(rigs["locked_joint_attrs"])),
    ]

    lines += [
        "",
        "### References",
        "- Total: {}".format(refs["count"]),
    ]
    for r in refs["references"]:
        status = "loaded" if r["loaded"] else "UNLOADED"
        missing = "" if r["file_exists"] else " ⚠ FILE MISSING"
        lines.append("  - `{}` [{}]{}".format(r["file_path"], status, missing))

    lines += [
        "",
        "### Unknown Nodes",
        "- Count: {}".format(unknown["count"]),
    ]
    for u in unknown["unknown_nodes"]:
        lines.append("  - `{}` (was type: `{}`)".format(u["node"], u["unknown_type"]))

    lines += [
        "",
        "### Animation",
        "- Anim curves: {}".format(anim["total_anim_curves"]),
        "- Curves with non-constant infinity: {}".format(anim["infinity_issue_count"]),
        "",
        "---",
        "Please analyse this scene, identify all problems, prioritise them by severity "
        "(Critical / Warning / Info), suggest fixes for each, and give an overall scene health score out of 10.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone test — run inside Maya's Script Editor to verify
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    report = run_scan()
    prompt = scan_to_prompt(report)
    print(prompt)

    # Optional: dump raw JSON for inspection
    # print(json.dumps(report, indent=2, default=str))

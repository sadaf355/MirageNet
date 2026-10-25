"""Generate a stylized MirageNet network-island hero and export GLB.

Usage (Blender 3.6+ / 4.x):
  blender --background --python tools/blender/generate_hero.py

Output: frontend/public/models/hero.glb
This script creates decorative geometry only; it does not replace the live Cytoscape topology.
"""
import bpy
import math
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'frontend', 'public', 'models', 'hero.glb')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
    for datablock in list(datablocks):
        if datablock.users == 0:
            datablocks.remove(datablock)

def material(name, color, metallic=0.2, roughness=0.35, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        # Blender 4.x renamed the emission socket; Blender 3.6 uses 'Emission'.
        emission_socket = bsdf.inputs.get('Emission Color') or bsdf.inputs.get('Emission')
        if emission_socket is not None:
            emission_socket.default_value = (*color, 1.0)
        strength_socket = bsdf.inputs.get('Emission Strength')
        if strength_socket is not None:
            strength_socket.default_value = emission
    return mat

navy = material('Midnight navy alloy', (0.035, 0.075, 0.12), 0.72, 0.3)
navy_top = material('Island top', (0.055, 0.11, 0.16), 0.45, 0.42)
teal = material('Signal teal', (0.12, 0.9, 0.72), 0.2, 0.25, 1.4)
blue = material('Data blue', (0.25, 0.52, 1.0), 0.15, 0.25, 1.1)
red = material('Alert coral', (1.0, 0.22, 0.31), 0.15, 0.25, 1.0)
gold = material('Backup amber', (1.0, 0.65, 0.25), 0.15, 0.25, 1.0)

# Floating beveled island base.
bpy.ops.mesh.primitive_cylinder_add(vertices=7, radius=3.1, depth=0.36, location=(0, 0, 0))
island = bpy.context.object
island.name = 'Network Island · beveled platform'
island.data.materials.append(navy)
bevel = island.modifiers.new('Soft machined edges', 'BEVEL'); bevel.width = 0.12; bevel.segments = 3
island.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
bpy.ops.mesh.primitive_cylinder_add(vertices=7, radius=2.75, depth=0.07, location=(0, 0, 0.21))
bpy.context.object.name = 'Island inner deck'; bpy.context.object.data.materials.append(navy_top)

def cylinder_between(name, a, b, radius, mat):
    mid = (Vector(a) + Vector(b)) / 2
    direction = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius, depth=direction.length, location=mid)
    obj = bpy.context.object; obj.name = name; obj.data.materials.append(mat)
    obj.rotation_mode = 'QUATERNION'; obj.rotation_quaternion = direction.to_track_quat('Z', 'Y')
    return obj

nodes = [
    ('WEB-01', (-2.1, .2, .52), teal), ('WS-01', (-1.1, .75, .58), teal),
    ('FS-01', (-.1, .2, .62), blue), ('JMP-01', (.1, 1.05, .66), red),
    ('DB-01', (1.2, .2, .64), red), ('GIT-01', (1.45, .8, .58), blue),
    ('BKP-01', (2.1, .15, .55), gold),
]
for idx, (name, pos, mat) in enumerate(nodes):
    # Small stylized server-rack block beneath each glowing node.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(pos[0], pos[1] - .22, .47))
    rack = bpy.context.object; rack.name = f'{name} rack'; rack.dimensions = (.38, .28, .38)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rack.data.materials.append(navy)
    bevel = rack.modifiers.new('Rack edge bevel', 'BEVEL'); bevel.width = .035; bevel.segments = 2
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=.16, location=pos)
    orb = bpy.context.object; orb.name = f'{name} signal node'; orb.data.materials.append(mat)
    for poly in orb.data.polygons: poly.use_smooth = True
    # Small front status lights on each rack.
    for light_i in range(3):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(pos[0] - .1 + light_i * .1, pos[1] - .365, .48))
        led = bpy.context.object; led.name = f'{name} status LED {light_i+1}'; led.dimensions = (.035, .018, .018)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); led.data.materials.append(mat)

edge_pairs = [(0,1),(1,2),(1,3),(2,6),(3,4),(3,5),(3,6)]
for a, b in edge_pairs:
    cylinder_between(f'Link {nodes[a][0]} to {nodes[b][0]}', nodes[a][1], nodes[b][1], .018, teal)

# Emissive deck ring.
bpy.ops.mesh.primitive_torus_add(major_radius=2.55, minor_radius=.018, major_segments=96, minor_segments=8, location=(0, 0, .27))
bpy.context.object.name = 'Teal perimeter signal'; bpy.context.object.data.materials.append(teal)

# Lighting and camera.
def area_light(name, loc, energy, color, size):
    data = bpy.data.lights.new(name, 'AREA'); data.energy = energy; data.color = color; data.shape = 'DISK'; data.size = size
    obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj); obj.location = loc
    obj.rotation_euler = (Vector((0, 0, 0.2)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
area_light('Mint key light', (1.5, -3.5, 6), 850, (.55, 1.0, .9), 5)
area_light('Blue rim light', (-4, 2.5, 3.5), 650, (.2, .45, 1.0), 4)
area_light('Warm fill', (4, 3, 2), 400, (1.0, .45, .28), 3)
cam_data = bpy.data.cameras.new('Hero camera'); cam = bpy.data.objects.new('Hero camera', cam_data); bpy.context.collection.objects.link(cam)
cam.location = (6.4, -8.2, 6.3); target = Vector((0, 0, .2)); cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam_data.lens = 52
scene = bpy.context.scene; scene.camera = cam
scene.render.engine = 'CYCLES'; scene.cycles.samples = 32
scene.render.resolution_x = 1200; scene.render.resolution_y = 900; scene.render.resolution_percentage = 100
scene.world.color = (.008, .015, .025)
scene.render.image_settings.file_format = 'PNG'
# Export decorative mesh objects only. Runtime Three.js provides portable lighting;
# area lights are intentionally omitted for Blender/glTF compatibility.
bpy.ops.object.select_all(action='DESELECT')
for obj in scene.objects:
    if obj.type == 'MESH':
        obj.select_set(True)
bpy.context.view_layer.objects.active = island
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_apply=True)
print(f'MirageNet hero GLB exported to: {OUT}')

import bpy
import os

# Reset Blender to factory settings (clear the scene)
bpy.ops.wm.read_factory_settings(use_empty=True)

# Get the current scene and rename it
scene = bpy.context.scene
scene.name = "PurpleCubeScene"

# Set render engine to Cycles and configure GPU with OptiX
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "OPTIX"
bpy.context.preferences.addons["cycles"].preferences.refresh_devices()
for device in bpy.context.preferences.addons["cycles"].preferences.devices:
    device.use = True

# Disable film transparency so the world background shows
scene.render.film_transparent = False

# Create a new world with a gray background and assign it to the scene
world = bpy.data.worlds.new("World_PurpleCube")
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    # Set background color to gray (R, G, B, Alpha)
    bg_node.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
scene.world = world

# Delete any default objects (if any remain)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create a purple cube at the origin (center of the scene)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
cube.name = "PurpleCube"

# Create a new material with a purple color and assign it to the cube
purple_mat = bpy.data.materials.new(name="PurpleMaterial")
purple_mat.use_nodes = True
nodes = purple_mat.node_tree.nodes
links = purple_mat.node_tree.links

# Remove any default nodes to set up a custom node tree
for node in nodes:
    nodes.remove(node)

# Create a Principled BSDF node for the purple material
bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.5, 0, 0.5, 1)  # Purple color
bsdf.inputs["Roughness"].default_value = 0.4

# Create the Material Output node
material_output = nodes.new(type="ShaderNodeOutputMaterial")
links.new(bsdf.outputs[0], material_output.inputs[0])
cube.data.materials.append(purple_mat)

# Add a camera so the cube is centered in the view.
# Place the camera at (0, 0, 10) so that it looks straight down toward the origin.
cam_data = bpy.data.cameras.new("Camera")
camera = bpy.data.objects.new("Camera", cam_data)
camera.location = (0, 0, 10)
# With default rotation (0,0,0), the camera looks along its -Z axis, i.e. toward (0,0,0)
scene.collection.objects.link(camera)
scene.camera = camera

# Add a Sun light to properly light the scene.
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light = bpy.data.objects.new(name="Sun", object_data=light_data)
light.location = (0, 10, 10)
scene.collection.objects.link(light)

# Set render resolution and file format
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'

# Set the output file path (renders to the current working directory)
output_filepath = os.path.join(os.getcwd(), "examples", "simple_render.png")
scene.render.filepath = output_filepath

# Render the scene and save the image
bpy.ops.render.render(write_still=True)
print("Rendered file saved to:", output_filepath)

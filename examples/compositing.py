import bpy
import os

# Ensure a clean slate
bpy.ops.wm.read_factory_settings(use_empty=True)

# Function to create a new scene with an object and a sun light
def create_scene(scene_name, obj_type, obj_location, color):
    scene = bpy.data.scenes.new(scene_name)
    bpy.context.window.scene = scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Set renderer to Cycles and enable GPU with OptiX
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'

    # Enable OptiX
    bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "OPTIX"
    bpy.context.preferences.addons["cycles"].preferences.refresh_devices()
    for device in bpy.context.preferences.addons["cycles"].preferences.devices:
        device.use = True  # Enable all GPU devices

    # Enable transparency (so backgrounds don't overwrite each other)
    scene.render.film_transparent = True  # Ensures background is transparent

    # Create the object
    if obj_type == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(location=obj_location)
    elif obj_type == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(location=obj_location)
    elif obj_type == 'CONE':
        bpy.ops.mesh.primitive_cone_add(location=obj_location)

    obj = bpy.context.object

    # Create a new material with nodes
    mat = bpy.data.materials.new(name=f"Material_{scene_name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove default Principled BSDF
    for node in nodes:
        nodes.remove(node)

    # Create unique materials for each object type
    if obj_type == "SPHERE":
        # Sphere: Glossy + Diffuse mix
        diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
        diffuse.inputs["Color"].default_value = color

        glossy = nodes.new(type="ShaderNodeBsdfGlossy")
        glossy.inputs["Color"].default_value = color
        glossy.inputs["Roughness"].default_value = 0.1

        fresnel = nodes.new(type="ShaderNodeFresnel")

        mix_shader = nodes.new(type="ShaderNodeMixShader")
        links.new(fresnel.outputs[0], mix_shader.inputs[0])
        links.new(diffuse.outputs[0], mix_shader.inputs[1])
        links.new(glossy.outputs[0], mix_shader.inputs[2])

        output = nodes.new(type="ShaderNodeOutputMaterial")
        links.new(mix_shader.outputs[0], output.inputs[0])

    elif obj_type == "CUBE":
        # Cube: Emission + Principled BSDF mix
        emission = nodes.new(type="ShaderNodeEmission")
        emission.inputs["Color"].default_value = color
        emission.inputs["Strength"].default_value = 2.0

        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.3

        mix_shader = nodes.new(type="ShaderNodeMixShader")
        mix_shader.inputs[0].default_value = 0.5  # Even mix

        links.new(emission.outputs[0], mix_shader.inputs[1])
        links.new(principled.outputs[0], mix_shader.inputs[2])

        output = nodes.new(type="ShaderNodeOutputMaterial")
        links.new(mix_shader.outputs[0], output.inputs[0])

    elif obj_type == "CONE":
        # Cone: Glass + Subsurface Scattering
        glass = nodes.new(type="ShaderNodeBsdfGlass")
        glass.inputs["Color"].default_value = color
        glass.inputs["Roughness"].default_value = 0.2
        glass.inputs["IOR"].default_value = 1.5

        sss = nodes.new(type="ShaderNodeSubsurfaceScattering")
        sss.inputs["Color"].default_value = color
        sss.inputs["Scale"].default_value = 0.1

        mix_shader = nodes.new(type="ShaderNodeMixShader")
        mix_shader.inputs[0].default_value = 0.4  # Glass dominates

        links.new(glass.outputs[0], mix_shader.inputs[1])
        links.new(sss.outputs[0], mix_shader.inputs[2])

        output = nodes.new(type="ShaderNodeOutputMaterial")
        links.new(mix_shader.outputs[0], output.inputs[0])

    obj.data.materials.append(mat)

    # Add a camera at the origin, looking towards -Z
    cam = bpy.data.objects.new(f"Camera_{scene_name}", bpy.data.cameras.new(f"Camera_{scene_name}"))
    cam.location = (0, 0, 0)
    cam.rotation_euler = (0, 0, 0)  # Looking forward towards -Z
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Add a Sun light at the origin, pointing toward -Z
    sun_light = bpy.data.objects.new(f"Sun_{scene_name}", bpy.data.lights.new(f"Sun_{scene_name}", 'SUN'))
    sun_light.location = (0, 0, 0)  # Place light at origin
    sun_light.rotation_euler = (0, 0, 0)  # Pointing along -Z
    scene.collection.objects.link(sun_light)

    return scene


# Create three scenes with objects positioned exactly as specified
scene_a = create_scene("Scene_A", "SPHERE", (-5, 2, -20), (0, 1, 0, 1))  # Green Sphere
scene_b = create_scene("Scene_B", "CUBE", (5, 2, -20), (1, 0, 0, 1))      # Red Cube
scene_c = create_scene("Scene_C", "CONE", (0, -2, -20), (0, 0, 1, 1))     # Blue Cone

# Keep all previous scene setup and rendering code...


# Create a composite scene
composite_scene = bpy.data.scenes.new("CompositeScene")
bpy.context.window.scene = composite_scene

# Enable nodes for compositing
composite_scene.use_nodes = True
tree = composite_scene.node_tree
nodes = tree.nodes
links = tree.links

# Clear default nodes
for node in nodes:
    nodes.remove(node)

# Create Scene Render Layer nodes
scene_nodes = {}
for i, scene in enumerate([scene_a, scene_b, scene_c]):
    node = nodes.new(type="CompositorNodeRLayers")
    node.scene = scene
    node.location = (-500, i * -200)
    scene_nodes[scene.name] = node

# Create Alpha Over nodes to blend the scenes properly
alpha_1 = nodes.new(type="CompositorNodeAlphaOver")
alpha_1.use_premultiply = True  # Ensure proper transparency blending
alpha_1.location = (100, -100)

alpha_2 = nodes.new(type="CompositorNodeAlphaOver")
alpha_2.use_premultiply = True
alpha_2.location = (300, -100)

# Composite output node
composite_output = nodes.new(type="CompositorNodeComposite")
composite_output.location = (600, -100)

# Viewer node (optional for preview)
viewer_node = nodes.new(type="CompositorNodeViewer")
viewer_node.location = (600, 100)

# Link nodes
links.new(scene_nodes["Scene_A"].outputs["Image"], alpha_1.inputs[1])  # Sphere first
links.new(scene_nodes["Scene_B"].outputs["Image"], alpha_1.inputs[2])  # Cube on top
links.new(alpha_1.outputs[0], alpha_2.inputs[1])
links.new(scene_nodes["Scene_C"].outputs["Image"], alpha_2.inputs[2])  # Cone last

links.new(alpha_2.outputs[0], composite_output.inputs[0])
links.new(alpha_2.outputs[0], viewer_node.inputs[0])

# Set render engine and OptiX for composite scene
composite_scene.render.engine = 'CYCLES'
composite_scene.cycles.device = 'GPU'

# Set render settings
composite_scene.render.resolution_x = 1920
composite_scene.render.resolution_y = 1080
composite_scene.render.resolution_percentage = 100
composite_scene.render.filepath = os.path.join(os.getcwd(), "examples", "composite_render.png")
composite_scene.render.image_settings.file_format = 'PNG'

# Save the blend file
blend_file_path = os.path.join(os.getcwd(), "examples", "composite_scene_optix.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_file_path)

# Render the compositing scene and save the output image
bpy.context.window.scene = composite_scene
bpy.ops.render.render(write_still=True)
print(f"Render saved to: {composite_scene.render.filepath}")


def load_and_render_blend(filepath):
    """
    Loads the saved .blend file and renders the scene.
    """
    if os.path.exists(filepath):
        # Load the .blend file
        bpy.ops.wm.open_mainfile(filepath=filepath)

        # Ensure the composite scene is set as the active scene
        if "CompositeScene" in bpy.data.scenes:
            bpy.context.window.scene = bpy.data.scenes["CompositeScene"]
        else:
            print("CompositeScene not found in the loaded blend file.")
            return

        # Ensure all objects in each scene are set as renderable
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                obj.hide_render = False  # Ensure the object is renderable

        # Ensure GPU rendering with OptiX is enabled after loading
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.device = 'GPU'

        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "OPTIX"
        bpy.context.preferences.addons["cycles"].preferences.refresh_devices()
        for device in bpy.context.preferences.addons["cycles"].preferences.devices:
            device.use = True

        # Ensure compositing is enabled
        bpy.context.scene.use_nodes = True

        # Set output file name with "reloaded" appended
        reloaded_filepath = os.path.join(os.getcwd(), "examples", "composite_render_reloaded.png")

        bpy.context.scene.render.filepath = reloaded_filepath
        bpy.context.scene.render.image_settings.file_format = 'PNG'

        # Render and save the output again
        bpy.ops.render.render(write_still=True)
        print(f"Re-rendered image saved to: {reloaded_filepath}")
    else:
        print(f"Blend file '{filepath}' not found.")


# Call the function to load and render the saved .blend file
load_and_render_blend(os.path.join(os.getcwd(), "examples", "composite_scene_optix.blend"))

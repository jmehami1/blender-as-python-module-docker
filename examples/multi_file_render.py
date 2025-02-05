import bpy
import os

# Ensure a clean slate.
bpy.ops.wm.read_factory_settings(use_empty=True)

def create_scene(scene_name, obj_type, obj_location, color):
    # Create a new scene and set it as active.
    scene = bpy.data.scenes.new(scene_name)
    bpy.context.window.scene = scene

    # Delete any default objects.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Set render engine and GPU/OptiX settings.
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "OPTIX"
    bpy.context.preferences.addons["cycles"].preferences.refresh_devices()
    for device in bpy.context.preferences.addons["cycles"].preferences.devices:
        device.use = True

    # Disable film transparency so that the world background is rendered.
    scene.render.film_transparent = False

    # Create a new world with a gray background and assign it to the scene.
    world = bpy.data.worlds.new(name="World_" + scene_name)
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        # Set to a gray color (RGB 0.5, 0.5, 0.5 with full opacity).
        bg_node.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    scene.world = world

    # Create the object based on the type.
    if obj_type == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(location=obj_location)
    elif obj_type == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(location=obj_location)
    elif obj_type == 'CONE':
        bpy.ops.mesh.primitive_cone_add(location=obj_location)
    obj = bpy.context.object

    # Create a new material with nodes.
    mat = bpy.data.materials.new(name=f"Material_{scene_name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove default nodes.
    for node in nodes:
        nodes.remove(node)

    # Create a different node setup based on object type.
    if obj_type == "SPHERE":
        # Sphere: mix of Diffuse and Glossy using a Fresnel factor.
        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        diffuse.inputs["Color"].default_value = color

        glossy = nodes.new("ShaderNodeBsdfGlossy")
        glossy.inputs["Color"].default_value = color
        glossy.inputs["Roughness"].default_value = 0.1

        fresnel = nodes.new("ShaderNodeFresnel")

        mix_shader = nodes.new("ShaderNodeMixShader")
        links.new(fresnel.outputs[0], mix_shader.inputs[0])
        links.new(diffuse.outputs[0], mix_shader.inputs[1])
        links.new(glossy.outputs[0], mix_shader.inputs[2])

        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(mix_shader.outputs[0], output.inputs[0])

    elif obj_type == "CUBE":
        # Cube: mix of Emission and Principled BSDF.
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = color
        emission.inputs["Strength"].default_value = 2.0

        principled = nodes.new("ShaderNodeBsdfPrincipled")
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.3

        mix_shader = nodes.new("ShaderNodeMixShader")
        mix_shader.inputs[0].default_value = 0.5  # Even mix factor.

        links.new(emission.outputs[0], mix_shader.inputs[1])
        links.new(principled.outputs[0], mix_shader.inputs[2])

        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(mix_shader.outputs[0], output.inputs[0])

    elif obj_type == "CONE":
        # Cone: mix of Glass and Subsurface Scattering.
        glass = nodes.new("ShaderNodeBsdfGlass")
        glass.inputs["Color"].default_value = color
        glass.inputs["Roughness"].default_value = 0.2
        glass.inputs["IOR"].default_value = 1.5

        sss = nodes.new("ShaderNodeSubsurfaceScattering")
        sss.inputs["Color"].default_value = color
        sss.inputs["Scale"].default_value = 0.1

        mix_shader = nodes.new("ShaderNodeMixShader")
        mix_shader.inputs[0].default_value = 0.4  # More weight for Glass.

        links.new(glass.outputs[0], mix_shader.inputs[1])
        links.new(sss.outputs[0], mix_shader.inputs[2])

        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(mix_shader.outputs[0], output.inputs[0])

    obj.data.materials.append(mat)

    # Add a camera at the origin, looking down the negative Z axis.
    cam_data = bpy.data.cameras.new(f"Camera_{scene_name}")
    cam = bpy.data.objects.new(f"Camera_{scene_name}", cam_data)
    cam.location = (0, 0, 0)
    cam.rotation_euler = (0, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Add a Sun light at the origin.
    sun_data = bpy.data.lights.new(name=f"Sun_{scene_name}", type='SUN')
    sun = bpy.data.objects.new(f"Sun_{scene_name}", sun_data)
    sun.location = (0, 0, 0)
    sun.rotation_euler = (0, 0, 0)
    scene.collection.objects.link(sun)

    return scene

# Create three individual scenes.
scene_a = create_scene("Scene_A", "SPHERE", (-5, 2, -20), (0, 1, 0, 1))  # Green sphere.
scene_b = create_scene("Scene_B", "CUBE", (5, 2, -20), (1, 0, 0, 1))       # Red cube.
scene_c = create_scene("Scene_C", "CONE", (0, -2, -20), (0, 0, 1, 1))      # Blue cone.

# Common render settings.
render_settings = {
    "resolution_x": 1920,
    "resolution_y": 1080,
    "resolution_percentage": 100,
    "engine": "CYCLES",
    "file_format": "PNG",
    "cycles_device": "GPU"
}

# Apply common render settings and GPU/OptiX settings to each scene.
scenes = [scene_a, scene_b, scene_c]
for scene in scenes:
    scene.render.engine = render_settings["engine"]
    scene.render.resolution_x = render_settings["resolution_x"]
    scene.render.resolution_y = render_settings["resolution_y"]
    scene.render.resolution_percentage = render_settings["resolution_percentage"]
    scene.render.image_settings.file_format = render_settings["file_format"]
    scene.cycles.device = render_settings["cycles_device"]

    bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "OPTIX"
    bpy.context.preferences.addons["cycles"].preferences.refresh_devices()
    for device in bpy.context.preferences.addons["cycles"].preferences.devices:
        device.use = True

# Render each scene individually with its gray background.
for scene in scenes:
    bpy.context.window.scene = scene
    filepath = os.path.join(os.getcwd(), "examples", f"{scene.name}_render.png")
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.name} saved to: {filepath}")

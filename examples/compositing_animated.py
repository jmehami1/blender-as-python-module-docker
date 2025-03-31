import bpy
import os
import random
import numpy as np
import imageio.v2 as imageio
from skimage import transform

# Ensure a clean slate
bpy.ops.wm.read_factory_settings(use_empty=True)

def create_scene(scene_name, obj_type, obj_location, color):
    """
    Create a new scene with a specified object and a sun light.

    The scene is set to use Cycles with GPU (OptiX) rendering, and transparency
    is enabled so that backgrounds do not overwrite each other. A new material
    is created and applied to the object.

    Parameters:
        scene_name (str): Name of the scene.
        obj_type (str): Type of object to create ('CUBE', 'SPHERE', or 'CONE').
        obj_location (tuple): Location where the object will be placed.
        color (tuple): RGBA color for the object's material.
    
    Returns:
        bpy.types.Scene: The newly created scene.
    """
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
    scene.render.film_transparent = True

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

    # Remove default nodes
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
    cam.rotation_euler = (0, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Add a Sun light at the origin, pointing toward -Z
    sun_light = bpy.data.objects.new(f"Sun_{scene_name}", bpy.data.lights.new(f"Sun_{scene_name}", 'SUN'))
    sun_light.location = (0, 0, 0)
    sun_light.rotation_euler = (0, 0, 0)
    scene.collection.objects.link(sun_light)

    return scene

def random_move_objects(scenes, move_range=0.5, frame=1, frequency=0.1):
    """
    Move mesh objects in the given scenes along smooth random trajectories.

    For each scene in `scenes`, this function iterates through all objects and,
    if the object is of type 'MESH', applies a sinusoidal offset along the X, Y, and Z axes,
    ensuring the object remains within the camera's field of view.

    Parameters:
        scenes (list of bpy.types.Scene): Scenes whose mesh objects will be moved.
        move_range (float): Maximum amplitude of the sinusoidal offset.
        frame (int): Current frame number to calculate the trajectory.
        frequency (float): Frequency of the sinusoidal motion.
    """

    for scene in scenes:
        for obj in scene.objects:
            if obj.type == 'MESH':
                # Smooth sinusoidal offsets
                offset_x = move_range * np.sin(frequency * frame + random.uniform(0, 2 * np.pi))
                offset_y = move_range * np.sin(frequency * frame + random.uniform(0, 2 * np.pi))
                offset_z = move_range * np.sin(frequency * frame + random.uniform(0, 2 * np.pi))

                # Ensure object stays within the FOV
                obj_x = obj.location.x + offset_x
                obj_y = obj.location.y + offset_y
                obj_z = obj.location.z + offset_z

                obj.location.x = obj_x
                obj.location.y = obj_y
                obj.location.z = obj_z

def render_animation(num_frames=10, output_dir="animation_example"):
    """
    Render an animation over a specified number of frames.

    For each frame, this function:
      1. Randomly moves objects in the object scenes.
      2. Updates the frame in all scenes to force dependency graph updates.
      3. Renders the composite scene (which composites the object scenes together).

    Parameters:
        num_frames (int): Number of frames to render.
        output_dir (str): Directory to save the rendered frames.
    """

    # Create the output directory if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    # List of scenes containing the objects to be moved (exclude the composite scene)
    object_scenes = [scene_a, scene_b, scene_c]

    # Ensure the composite scene is the active scene for rendering
    bpy.context.window.scene = composite_scene

    frame_filepaths = []

    for frame in range(1, num_frames + 1):
        print(f"Rendering frame {frame}...")

        image_path = os.path.join(output_dir, f"img_{frame:03d}.png")

        composite_scene.render.filepath = image_path
        # Randomly move objects in each object scene
        random_move_objects(object_scenes, move_range=0.5, frame=frame)
        
        # Update the frame for all scenes to force an update of the dependency graph
        for scene in [scene_a, scene_b, scene_c, composite_scene]:
            scene.frame_set(frame)
        
        # Render the composite scene to an off-screen buffer
        bpy.ops.render.render(write_still=True)

        frame_filepaths.append(image_path)

    return frame_filepaths


def create_video_from_frames(frame_filepaths, output_filepath="animation.mp4", fps=24):
    """
    Create a video from a list of frame file paths.

    Parameters:
        frame_filepaths (list of str): List of file paths to the frames.
        output_filepath (str): File path for the output video.
        fps (int): Frames per second for the video.
    """
    if not frame_filepaths:
        raise ValueError("No frame file paths provided.")
    
    # get first image to determine size
    first_image = imageio.imread(frame_filepaths[0])
    height, width, _ = first_image.shape

    #image width and height need to be divisible by 16. Resize if not
    if width % 16 != 0:
        width = (width // 16) * 16
    if height % 16 != 0:
        height = (height // 16) * 16

    writer = imageio.get_writer(output_filepath, fps=fps)
    
    # load images
    for i, frame_filepath in enumerate(frame_filepaths):
        if not os.path.isfile(frame_filepath):
            raise FileNotFoundError(f"Frame file {frame_filepath} does not exist.")
        if not frame_filepath.lower().endswith(('.png', '.jpg', '.jpeg')):
            raise ValueError(f"Frame file {frame_filepath} is not a valid image format.")\
            
        image = imageio.imread(frame_filepath)
        image = transform.resize(image, (height, width), mode='reflect')
        image = (image * 255).astype(np.uint8)
        writer.append_data(image)

    writer.close()
    print(f"Video saved to: {output_filepath}")

def set_composite_scene_properties(resolution_x=1920, resolution_y=1080, samples=1000):

        # List of scenes containing the objects to be moved (exclude the composite scene)
    object_scenes = [scene_a, scene_b, scene_c, composite_scene]

    for scene in object_scenes:
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        scene.render.resolution_x = resolution_x
        scene.render.resolution_y = resolution_y
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.cycles.samples = samples

if __name__ == "__main__":
    # Create three scenes with objects positioned exactly as specified
    scene_a = create_scene("Scene_A", "SPHERE", (-5, 2, -20), (0, 1, 0, 1))  # Green Sphere
    scene_b = create_scene("Scene_B", "CUBE", (5, 2, -20), (1, 0, 0, 1))      # Red Cube
    scene_c = create_scene("Scene_C", "CONE", (0, -2, -20), (0, 0, 1, 1))     # Blue Cone

    # Create a composite scene that will composite the other three scenes
    composite_scene = bpy.data.scenes.new("CompositeScene")
    bpy.context.window.scene = composite_scene

    # Add a camera to the composite scene if not already present
    if not composite_scene.camera:
        composite_camera = bpy.data.objects.new("CompositeCamera", bpy.data.cameras.new("CompositeCamera"))
        composite_camera.location = (0, 0, 10)  # Position the camera
        composite_camera.rotation_euler = (0, 0, 0)  # Point towards -Z
        composite_scene.collection.objects.link(composite_camera)
        composite_scene.camera = composite_camera

    # Enable nodes for compositing
    composite_scene.use_nodes = True
    tree = composite_scene.node_tree
    nodes = tree.nodes
    links = tree.links

    # Clear default nodes
    for node in nodes:
        nodes.remove(node)

    # Create Scene Render Layer nodes for the three object scenes
    scene_nodes = {}
    for i, scene in enumerate([scene_a, scene_b, scene_c]):
        node = nodes.new(type="CompositorNodeRLayers")
        node.scene = scene
        node.location = (-500, i * -200)
        scene_nodes[scene.name] = node

    # Create Alpha Over nodes to blend the scenes properly
    alpha_1 = nodes.new(type="CompositorNodeAlphaOver")
    alpha_1.use_premultiply = True
    alpha_1.location = (100, -100)

    alpha_2 = nodes.new(type="CompositorNodeAlphaOver")
    alpha_2.use_premultiply = True
    alpha_2.location = (300, -100)

    # Composite output node
    composite_output = nodes.new(type="CompositorNodeComposite")
    composite_output.location = (700, -100)

    # Viewer node (optional for preview)
    viewer_node = nodes.new(type="CompositorNodeViewer")
    viewer_node.location = (700, 100)

    # Link nodes to composite the scenes
    links.new(scene_nodes["Scene_A"].outputs["Image"], alpha_1.inputs[1])  # Sphere first
    links.new(scene_nodes["Scene_B"].outputs["Image"], alpha_1.inputs[2])  # Cube on top
    links.new(alpha_1.outputs[0], alpha_2.inputs[1])
    links.new(scene_nodes["Scene_C"].outputs["Image"], alpha_2.inputs[2])  # Cone last

    # Add a gray background to the composite
    gray_background = nodes.new(type="CompositorNodeRGB")
    gray_background.outputs[0].default_value = (0.5, 0.5, 0.5, 1)  # Gray color in RGBA
    gray_background.location = (-100, -100)

    # New Alpha Over node to composite the gray background with the combined scenes
    alpha_gray = nodes.new(type="CompositorNodeAlphaOver")
    alpha_gray.use_premultiply = True
    alpha_gray.location = (500, -100)

    links.new(gray_background.outputs[0], alpha_gray.inputs[1])  # Gray background as bottom layer
    links.new(alpha_2.outputs[0], alpha_gray.inputs[2])           # Combined scenes as top layer

    # Final output linking
    links.new(alpha_gray.outputs[0], composite_output.inputs[0])
    links.new(alpha_gray.outputs[0], viewer_node.inputs[0])

    # Set render engine and device settings for the composite scene
    set_composite_scene_properties(resolution_x=720, resolution_y=480, samples=1000)


    ###############################################################################
    # Render 10 frames of the composite animation and create a video
    ###############################################################################
    output_dir = "animation_example"
    frame_filepaths = render_animation(150, output_dir)
    animation_path = os.path.join(output_dir, "composite_animation.mp4")
    create_video_from_frames(frame_filepaths, output_filepath=animation_path, fps=10)
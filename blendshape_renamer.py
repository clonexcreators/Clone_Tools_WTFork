import bpy

# Define the search strings and their replacements
search_replacements = {
    "browdownleft": "BrowDownLeft",
    "browdownright": "BrowDownRight",
    "browinnerup": "BrowInnerUp",
    "browouterupleft": "BrowOuterUpLeft",
    "browouterupright": "BrowOuterUpRight",
    "cheekpuff": "CheekPuff",
    "cheeksquintleft": "CheekSquintLeft",
    "cheeksquintright": "CheekSquintRight",
    "eyeblinkleft": "EyeBlinkLeft",
    "eyeblinkright": "EyeBlinkRight",
    "eyelookdownleft": "EyeLookDownLeft",
    "eyelookdownright": "EyeLookDownRight",
    "eyelookinleft": "EyeLookInLeft",
    "eyelookinright": "EyeLookInRight",
    "eyelookoutleft": "EyeLookOutLeft",
    "eyelookoutright": "EyeLookOutRight",
    "eyelookupleft": "EyeLookUpLeft",
    "eyelookupright": "EyeLookUpRight",
    "eyesquintleft": "EyeSquintLeft",
    "eyesquintright": "EyeSquintRight",
    "eyewideleft": "EyeWideLeft",
    "eyewideright": "EyeWideRight",
    "jawforward": "JawForward",
    "jawleft": "JawLeft",
    "jawopen": "JawOpen",
    "jawright": "JawRight",
    "mouthclose": "MouthClose",
    "mouthdimpleleft": "MouthDimpleLeft",
    "mouthdimpleright": "MouthDimpleRight",
    "mouthfrownleft": "MouthFrownLeft",
    "mouthfrownright": "MouthFrownRight",
    "mouthfunnel": "MouthFunnel",
    "mouthleft": "MouthLeft",
    "mouthlowerdownleft": "MouthLowerDownLeft",
    "mouthlowerdownright": "MouthLowerDownRight",
    "mouthpressleft": "MouthPressLeft",
    "mouthpressright": "MouthPressRight",
    "mouthpucker": "MouthPucker",
    "mouthright": "MouthRight",
    "mouthrolllower": "MouthRollLower",
    "mouthrollupper": "MouthRollUpper",
    "mouthshruglower": "MouthShrugLower",
    "mouthshrugupper": "MouthShrugUpper",
    "mouthsmileleft": "MouthSmileLeft",
    "mouthsmileright": "MouthSmileRight",
    "mouthstretchleft": "MouthStretchLeft",
    "mouthstretchright": "MouthStretchRight",
    "mouthupperupleft": "MouthUpperUpLeft",
    "mouthupperupright": "MouthUpperUpRight",
    "nosesneerleft": "NoseSneerLeft",
    "nosesneerright": "NoseSneerRight",
    "tongueout": "TongueOut"
    # Add more entries as needed
}

try:
    # Iterate through all objects in the scene
    for obj in bpy.data.objects:
        # Check if the object has a shape key collection
        if obj.type == "MESH" and obj.data.shape_keys:
            shape_keys = obj.data.shape_keys.key_blocks

            # Iterate through the shape keys
            for shape_key in shape_keys:
                # Iterate through the search strings and replacements
                for search_string, replacement in search_replacements.items():
                    # Perform a case-insensitive search and replace
                    if search_string.lower() in shape_key.name.lower():
                        shape_key.name = replacement

    # Update the scene to reflect the changes
    bpy.context.view_layer.update()

    # Print the modified shape key names
    print("Modified Shape Key Names:")
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.data.shape_keys:
            shape_keys = obj.data.shape_keys.key_blocks
            for shape_key in shape_keys:
                print(shape_key.name)

    print("Script execution completed.")

except Exception as e:
    print("An error occurred during script execution:")
    print(str(e))
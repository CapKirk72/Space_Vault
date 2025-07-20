import json

def load_hitbox_from_json(filepath: str) -> list[dict]:
    """
    Loads hitbox definitions from a JSON file.

    Each definition in the JSON should be a dictionary representing a shape
    (e.g., {"type": "circle", "local_x": 0, "local_y": -10, "radius": 5} or
     {"type": "square", "local_x": 0, "local_y": 10, "width": 20, "height": 10, "local_angle_degrees": 0}).

    Args:
        filepath (str): The path to the JSON file.

    Returns:
        list[dict]: A list of shape definition dictionaries.
                    Returns an empty list if the file is not found or is invalid.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            if isinstance(data, list): # Ensure the top-level structure is a list
                # Basic validation for required keys could be added here if desired
                return data
            else:
                print(f"Error: Hitbox JSON {filepath} should contain a list of shapes.")
                return []
    except FileNotFoundError:
        print(f"Error: Hitbox file not found at {filepath}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in hitbox file at {filepath}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading hitbox {filepath}: {e}")
        return []

if __name__ == '__main__':
    # Example usage (assuming you create this example file)
    # First, create a dummy assets/hitboxes/test_hitbox.json
    # Example content for test_hitbox.json:
    # [
    #   {"type": "circle", "local_x": 0, "local_y": 0, "radius": 10},
    #   {"type": "square", "local_x": 10, "local_y": 10, "width": 5, "height": 5, "local_angle_degrees": 45}
    # ]
    
    # To run this example, you would:
    # 1. Create the 'assets/hitboxes' directory if it doesn't exist.
    # 2. Create a file 'assets/hitboxes/test_hitbox.json' with the content above.
    # 3. Uncomment and run the lines below.
    
    # import os
    # if not os.path.exists("assets/hitboxes"):
    #     os.makedirs("assets/hitboxes")
    # example_hitbox_data = [
    #    {"type": "circle", "local_x": 0, "local_y": 0, "radius": 10},
    #    {"type": "square", "local_x": 10, "local_y": 10, "width": 5, "height": 5, "local_angle_degrees": 45}
    # ]
    # with open("assets/hitboxes/test_hitbox.json", "w") as f_example:
    #    json.dump(example_hitbox_data, f_example, indent=2)

    # loaded_shapes = load_hitbox_from_json("assets/hitboxes/test_hitbox.json")
    # if loaded_shapes:
    #    print("Successfully loaded hitbox shapes:")
    #    for shape in loaded_shapes:
    #        print(shape)
    # else:
    #    print("Failed to load hitbox shapes or file was empty/invalid.")
    pass # Keep the pass for now if not running the example 
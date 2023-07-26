import json
import inspect

def save_as_json(raw_data, file_name):
    with open(file_name, "w") as f:
        json.dump(raw_data, f, indent=4, ensure_ascii=False)

def load_json(file_name) -> dict:
    with open(file_name, "r") as f:
        return json.load(f)
    
def generate_schema(function):
    signature = inspect.signature(function)
    params = signature.parameters
    
    properties = {}
    required = []
    for name, param in params.items():
        param_info = {"type": "string"}  # Assuming all parameters are strings, adjust as needed
        if param.default != inspect.Parameter.empty:
            param_info["enum"] = [param.default]
        else:
            required.append(name)
        properties[name] = param_info

    schema = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    return schema
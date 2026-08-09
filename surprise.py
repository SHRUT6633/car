import sys
import os

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
YAML_PATH = os.path.join(CONFIG_DIR, "surprise_rules.yaml")

def read_yaml(path):
    rules = {}
    if not os.path.exists(path):
        return rules
    with open(path, "r") as f:
        for line in f:
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("#"):
                continue
            # Remove comments after values
            if "#" in line_strip:
                line_strip = line_strip.split("#")[0].strip()
            if ":" in line_strip:
                parts = line_strip.split(":", 1)
                key = parts[0].strip()
                val = parts[1].strip()
                # Parse types
                if val.lower() == "true":
                    rules[key] = True
                elif val.lower() == "false":
                    rules[key] = False
                elif val.startswith('"') and val.endswith('"'):
                    rules[key] = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    rules[key] = val[1:-1]
                else:
                    try:
                        if "." in val:
                            rules[key] = float(val)
                        else:
                            rules[key] = int(val)
                    except ValueError:
                        rules[key] = val
    return rules

def write_yaml(path, rules):
    # We read the original lines and replace values to preserve comments
    lines = []
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("#"):
            new_lines.append(line)
            continue
        
        # Parse key
        parts = line.split(":", 1)
        key = parts[0].strip()
        if key in rules:
            comment = ""
            if "#" in parts[1]:
                comment = "  #" + parts[1].split("#", 1)[1].rstrip()
            
            val = rules[key]
            if isinstance(val, bool):
                val_str = "true" if val else "false"
            elif isinstance(val, str):
                val_str = f'"{val}"'
            else:
                val_str = str(val)
                
            new_lines.append(f"{key}: {val_str}{comment}\n")
            updated_keys.add(key)
        else:
            new_lines.append(line)
            
    # Add any missing keys
    for key, val in rules.items():
        if key not in updated_keys:
            if isinstance(val, bool):
                val_str = "true" if val else "false"
            elif isinstance(val, str):
                val_str = f'"{val}"'
            else:
                val_str = str(val)
            new_lines.append(f"{key}: {val_str}\n")
            
    with open(path, "w") as f:
        f.writelines(new_lines)

def print_help():
    print("==================================================")
    print("      WRO 2026 MATCH-DAY SURPRISE RULES TUNER     ")
    print("==================================================")
    print("Usage:")
    print("  python surprise.py                     -> Print current rules")
    print("  python surprise.py [KEY] [VALUE]       -> Set a single rule")
    print("  python surprise.py --direction [CW/CCW] --sign [NORMAL/REVERSED] ...")
    print("\nAvailable Keys & Options:")
    print("  SIGN_LOGIC           : NORMAL | REVERSED (swaps red/green pillar logic)")
    print("  DRIVING_DIRECTION    : CW | CCW")
    print("  NARROW_TRACK_MODE    : true | false")
    print("  STOP_AND_GO_ENABLED  : true | false")
    print("  STOP_DURATION_SEC    : float (e.g. 3.0)")
    print("  EMERGENCY_BRAKE_DIST_MM: int (e.g. 180)")
    print("  PARKING_SIDE         : LEFT | RIGHT | DYNAMIC")
    print("  START_FROM_PARKING   : true | false")

def main():
    if not os.path.exists(YAML_PATH):
        print(f"[ERROR] surprise_rules.yaml not found at {YAML_PATH}")
        return

    rules = read_yaml(YAML_PATH)

    args = sys.argv[1:]
    if not args:
        print_help()
        print("\n--- Current Match-Day Settings ---")
        for k, v in rules.items():
            print(f"  {k:24}: {v}")
        return

    if args[0] in ("-h", "--help", "help"):
        print_help()
        return

    # Parse arguments
    updated = {}
    if len(args) == 2:
        # Single key value set: python surprise.py SIGN_LOGIC REVERSED
        key = args[0].upper()
        val = args[1]
        updated[key] = val
    else:
        # Command line arguments like: python surprise.py --direction CW --sign REVERSED
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("--"):
                key = arg[2:].upper().replace("-", "_")
                if key == "DIRECTION":
                    key = "DRIVING_DIRECTION"
                elif key == "SIGN":
                    key = "SIGN_LOGIC"
                elif key == "NARROW":
                    key = "NARROW_TRACK_MODE"
                elif key == "STOP_AND_GO":
                    key = "STOP_AND_GO_ENABLED"
                elif key == "STOP_DURATION":
                    key = "STOP_DURATION_SEC"
                elif key == "EMERGENCY_DIST":
                    key = "EMERGENCY_BRAKE_DIST_MM"
                
                if i + 1 < len(args):
                    val = args[i + 1]
                    updated[key] = val
                    i += 2
                else:
                    print(f"[ERROR] Missing value for argument {arg}")
                    return
            else:
                print(f"[ERROR] Invalid argument format: {arg}")
                return

    # Apply updates with type conversion
    for k, v in updated.items():
        if k not in rules:
            print(f"[WARN] Adding new key: {k}")
        
        # Convert types to match existing or expected schema
        if str(v).lower() in ("true", "1", "yes"):
            rules[k] = True
        elif str(v).lower() in ("false", "0", "no"):
            rules[k] = False
        else:
            try:
                if "." in str(v):
                    rules[k] = float(v)
                else:
                    rules[k] = int(v)
            except ValueError:
                rules[k] = str(v)
        print(f"[SET] {k} -> {rules[k]}")

    write_yaml(YAML_PATH, rules)
    print("[SUCCESS] surprise_rules.yaml updated successfully.")

if __name__ == "__main__":
    main()

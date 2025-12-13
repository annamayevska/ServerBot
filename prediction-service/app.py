#aggregate a structured dataset for model training 
import json
from pathlib import Path
from input_properties import compute_input_properties
from output_properties import calculate_overall

# -------------------- Main Processing --------------------
def main():
    BASE_DIR = Path(__file__).parent.resolve()
    LOG_FOLDER = BASE_DIR / ".." / "dataset_large_"
    DATASET_FILE = BASE_DIR / "test_large.json" 

    if not LOG_FOLDER.exists():
        print(f"[ERROR] data_logs folder not found: {LOG_FOLDER}")
        return

    yaml_files = sorted(LOG_FOLDER.glob("*.yaml"))
    if not yaml_files:
        print("[WARN] No YAML files found in data_logs.")
        return

    all_results = {}
    dataset = []

    for file_path in yaml_files:
        print(f"\n[INFO] Processing file: {file_path.name}")

        # --- Input properties ---
        input_props = compute_input_properties(file_path=file_path)  
        print("[INFO] Input properties:")
        print(json.dumps(input_props, indent=4))

        # --- Output properties ---
        output_props = calculate_overall(file_path)  
        print("[INFO] Output properties:")
        print(json.dumps(output_props, indent=4))

        all_results[file_path.name] = {
            "input_properties": input_props,
            "output_properties": output_props
        }

        row = {
            "file_name": file_path.name,
            "input_features": input_props,
            "output_features": output_props
        }
        dataset.append(row)


    with open(DATASET_FILE, "w") as f:
        json.dump(dataset, f, indent=4)

    print(f"\n[INFO] Dataset saved to {DATASET_FILE}, total entries: {len(dataset)}")
    print("\n[INFO] All files processed. Summary:")
    print(json.dumps(all_results, indent=4))


if __name__ == "__main__":
    main()

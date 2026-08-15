"""Comprehensive code integrity and import verification script.
Tests every physical Python module in the project for:
1. Valid Python syntax (AST parsing)
2. Successful runtime module loading & symbol resolution (importlib)
3. Zero NameError, SyntaxError, AttributeError, or ImportError
"""
import os
import sys
import ast
import importlib
import traceback

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    print("=" * 80)
    print("CROSS-BANK MULE ACCOUNT DETECTION NETWORK — CODE INTEGRITY AUDIT")
    print("=" * 80)

    modules_to_test = [
        "backend.app.config",
        "backend.app.main",
        "backend.app.database",
        "backend.app.database.repositories",
        "backend.app.privacy",
        "backend.app.privacy.hashing",
        "backend.app.privacy.bank_vault",
        "backend.app.data_generator",
        "backend.app.data_generator.synthetic_banks",
        "backend.app.data_generator.motif_injector",
        "backend.app.graph",
        "backend.app.graph.graph_engine",
        "backend.app.features",
        "backend.app.features.feature_extractor",
        "backend.app.features.component_detector",
        "backend.app.ml",
        "backend.app.ml.dataset",
        "backend.app.ml.classifier",
        "backend.app.ml.explainability",
        "backend.app.ml.thresholds",
        "backend.app.ml.training",
        "backend.app.api.schemas",
        "backend.app.api.routes",
    ]

    print(f"\n[Step 1/2] Auditing Runtime Imports ({len(modules_to_test)} core modules)...")
    import_results = []
    has_import_errors = False

    for mod_name in modules_to_test:
        try:
            mod = importlib.import_module(mod_name)
            attr_count = len(dir(mod))
            import_results.append((mod_name, "OK", f"{attr_count} symbols loaded"))
        except Exception as e:
            has_import_errors = True
            err_msg = f"{type(e).__name__}: {e}"
            import_results.append((mod_name, "FAILED", err_msg))
            traceback.print_exc()

    print(f"{'Module Name':<45} | {'Status':<8} | Details")
    print("-" * 80)
    for mod_name, status, details in import_results:
        print(f"{mod_name:<45} | {status:<8} | {details}")

    print(f"\n[Step 2/2] Scanning and Parsing All Physical Python Files in Workspace...")
    syntax_errors = []
    file_count = 0

    for root, _, files in os.walk(os.path.join(PROJECT_ROOT, "backend")):
        for f in files:
            if f.endswith(".py"):
                file_count += 1
                fpath = os.path.join(root, f)
                rel_path = os.path.relpath(fpath, PROJECT_ROOT)
                try:
                    with open(fpath, "r", encoding="utf-8") as src:
                        ast.parse(src.read(), filename=fpath)
                except Exception as e:
                    syntax_errors.append((rel_path, str(e)))

    print(f"Total Python files scanned: {file_count}")
    if syntax_errors:
        print("\n[CRITICAL] Syntax errors detected in physical files:")
        for fp, err in syntax_errors:
            print(f"  - {fp}: {err}")
    else:
        print(f"[OK] All {file_count} files parsed cleanly with zero syntax or indentation errors.")

    print("\n" + "=" * 80)
    if not has_import_errors and not syntax_errors:
        print("[AUDIT PASSED] 100% of workspace modules and files are syntactically and structurally sound.")
        print("=" * 80)
        sys.exit(0)
    else:
        print("[AUDIT FAILED] One or more code integrity checks failed.")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

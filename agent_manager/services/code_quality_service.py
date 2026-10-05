"""
Code Quality, Readability, Simplicity & Testability Metrics Service.
Analyzes code complexity, function lengths, directory distribution, and testability.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


def analyze_python_file(file_path: Path) -> Dict[str, Any]:
    """Analyzes a single Python file for LOC, functions, and function length metrics."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return {"loc": 0, "functions": [], "error": True}

    lines = content.splitlines()
    total_loc = len(lines)
    functions = []

    try:
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                fn_loc = max(1, end - start + 1)
                functions.append({
                    "name": node.name,
                    "file": file_path.name,
                    "loc": fn_loc,
                    "start_line": start,
                    "end_line": end
                })
    except Exception:
        pass

    return {
        "file": file_path.name,
        "path": str(file_path),
        "loc": total_loc,
        "functions": functions
    }


def compute_readability_and_simplicity_metrics(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Calculates structural metrics: LOC per file, LOC per function, and file distributions."""
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    src_dir = root / "agent_manager"

    # 1. Root folder file count
    root_files = [f.name for f in root.iterdir() if f.is_file()]
    root_file_count = len(root_files)

    # 2. Files per directory distribution
    dir_distribution: Dict[str, int] = {}
    all_py_files: List[Path] = []
    
    for r, dirs, files in os.walk(src_dir):
        # Exclude caches
        if "__pycache__" in r:
            continue
        rel_dir = os.path.relpath(r, root)
        py_files = [f for f in files if f.endswith(".py")]
        dir_distribution[rel_dir.replace("\\", "/")] = len(files)
        all_py_files.extend([Path(r) / f for f in py_files])

    # 3. File and Function LOC analysis
    file_analyses = [analyze_python_file(p) for p in all_py_files]
    total_loc = sum(f["loc"] for f in file_analyses)
    total_files = len(file_analyses)
    avg_loc_per_file = round(total_loc / total_files, 1) if total_files else 0.0

    all_functions = []
    for f in file_analyses:
        all_functions.extend(f["functions"])

    total_funcs = len(all_functions)
    avg_loc_per_func = round(sum(fn["loc"] for fn in all_functions) / total_funcs, 1) if total_funcs else 0.0

    # Top largest files and functions
    largest_files = sorted(file_analyses, key=lambda x: x["loc"], reverse=True)[:5]
    largest_functions = sorted(all_functions, key=lambda x: x["loc"], reverse=True)[:5]
    bloated_functions = [fn for fn in all_functions if fn["loc"] > 40]

    # Simplicity Score (0-100%)
    file_penalty = max(0, (avg_loc_per_file - 120) * 0.5)
    func_penalty = len(bloated_functions) * 2.0
    root_penalty = max(0, (root_file_count - 15) * 1.5)
    simplicity_score = round(max(0.0, min(100.0, 100.0 - (file_penalty + func_penalty + root_penalty))), 1)

    return {
        "simplicity_score": simplicity_score,
        "root_file_count": root_file_count,
        "directory_file_distribution": dir_distribution,
        "total_source_files": total_files,
        "total_lines_of_code": total_loc,
        "avg_lines_per_file": avg_loc_per_file,
        "max_lines_in_file": largest_files[0]["loc"] if largest_files else 0,
        "total_functions": total_funcs,
        "avg_lines_per_function": avg_loc_per_func,
        "max_lines_in_function": largest_functions[0]["loc"] if largest_functions else 0,
        "bloated_functions_count": len(bloated_functions),
        "largest_files": [{"file": f["file"], "loc": f["loc"]} for f in largest_files],
        "largest_functions": [{"name": fn["name"], "file": fn["file"], "loc": fn["loc"]} for fn in largest_functions]
    }


def compute_testability_metrics(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Calculates test coverage density, unit vs integration test distribution, and testability ratio."""
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    tests_dir = root / "tests"

    if not tests_dir.exists():
        return {"testability_score": 0.0, "total_tests": 0}

    test_files = [f for f in tests_dir.glob("test_*.py")]
    unit_tests = 0
    integration_tests = 0
    total_test_cases = 0
    test_loc = 0

    for tf in test_files:
        try:
            content = tf.read_text(encoding="utf-8")
            test_loc += len(content.splitlines())
            tree = ast.parse(content, filename=str(tf))
            is_integration = "TestClient" in content or "create_subprocess" in content
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        total_test_cases += 1
                        if is_integration:
                            integration_tests += 1
                        else:
                            unit_tests += 1
        except Exception:
            continue

    # Source LOC for ratio
    src_dir = root / "agent_manager"
    src_loc = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in src_dir.rglob("*.py") if "__pycache__" not in str(p))
    test_to_code_ratio = round(test_loc / src_loc, 2) if src_loc else 0.0

    # Testability Score: rewards test density and balance
    target_ratio = 0.8
    ratio_score = min(50.0, (test_to_code_ratio / target_ratio) * 50.0)
    density_score = min(50.0, total_test_cases * 0.5)
    testability_score = round(min(100.0, ratio_score + density_score), 1)

    return {
        "testability_score": testability_score,
        "total_test_files": len(test_files),
        "total_test_cases": total_test_cases,
        "unit_test_cases": unit_tests,
        "integration_test_cases": integration_tests,
        "total_test_lines_of_code": test_loc,
        "source_lines_of_code": src_loc,
        "test_to_code_ratio": test_to_code_ratio,
        "test_density_per_source_file": round(total_test_cases / max(1, len(list(src_dir.rglob("*.py")))), 2)
    }


def generate_code_health_report(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Produces the comprehensive Code Quality, Readability, and Testability report."""
    readability = compute_readability_and_simplicity_metrics(repo_root)
    testability = compute_testability_metrics(repo_root)

    composite_score = round((readability["simplicity_score"] * 0.5) + (testability["testability_score"] * 0.5), 1)

    return {
        "composite_code_health_score": composite_score,
        "readability_and_simplicity": readability,
        "testability_and_coverage": testability,
        "recommendations": [
            f"Refactor {readability['largest_files'][0]['file']} ({readability['largest_files'][0]['loc']} LOC) to bring under 200 lines." if readability['largest_files'] and readability['largest_files'][0]['loc'] > 250 else "All files within LOC budget.",
            f"Review {readability['bloated_functions_count']} functions exceeding 40 LOC." if readability['bloated_functions_count'] > 0 else "All functions compact (< 40 LOC).",
            f"Keep root directory uncluttered (currently {readability['root_file_count']} files; recommended <= 15)." if readability['root_file_count'] > 15 else "Root directory well-organized."
        ]
    }

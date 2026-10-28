"""Tests for scripts/prettier-config.mjs: Prettier options inferred from a repo's code, and
the refusal to touch a repo that already configures Prettier.

Each test builds a throwaway git repo in tmp_path and runs the script with node, so what is
checked is the config a consumer's foundry-init would write.
"""

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prettier-config.mjs"


def repo(tmp_path, files):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def run(cwd, *args):
    return subprocess.run(
        ["node", str(SCRIPT), *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def scaffold(tmp_path, files):
    run(repo(tmp_path, files))
    return json.loads((tmp_path / ".prettierrc.json").read_text(encoding="utf-8"))


SEMI_DOUBLE_2 = """import { a } from "./a";

export function f(x: number): number {
  const y = {
    name: "y",
    size: x,
  };
  if (x > 1) {
    return g(
      y.size,
      x
    );
  }
  return y.size;
}
"""

NO_SEMI_SINGLE_4 = """import { a } from './a'

export function f(x) {
    const y = {
        name: 'y',
        size: x,
    }
    if (x > 1) {
        return g(
            y.size,
            x,
        )
    }
    return y.size
}
"""


def test_infers_semicolon_free_single_quoted_four_space_code(tmp_path):
    config = scaffold(tmp_path, {"src/a.js": NO_SEMI_SINGLE_4})
    assert (config["semi"], config["singleQuote"], config["tabWidth"]) == (False, True, 4)


def test_infers_semicolon_double_quoted_two_space_code(tmp_path):
    config = scaffold(tmp_path, {"src/a.ts": SEMI_DOUBLE_2})
    assert (config["semi"], config["singleQuote"], config["tabWidth"]) == (True, False, 2)


def test_block_endings_do_not_read_as_missing_trailing_commas(tmp_path):
    # Many statement-then-`}` lines, every multi-line object with a trailing comma, and the
    # one multi-line call without one: es5, not "none".
    body = "\n".join(
        f"export function f{i}() {{\n  const o = {{\n    k: {i},\n  }};\n  return o;\n}}" for i in range(20)
    )
    config = scaffold(tmp_path, {"src/a.ts": body + "\n" + SEMI_DOUBLE_2})
    assert config["trailingComma"] == "es5"


def test_trailing_commas_in_calls_mean_all(tmp_path):
    config = scaffold(tmp_path, {"src/a.js": NO_SEMI_SINGLE_4})
    assert config["trailingComma"] == "all"
    assert config["overrides"] == [{"files": "*.jsonc", "options": {"trailingComma": "none"}}]


def test_print_width_is_the_narrowest_bucket_the_code_fits(tmp_path):
    # Code formatted at 100 columns: a minority of lines between 81 and 100, none past it.
    lines = [f"export const v{i} = '{'x' * 70}';" for i in range(10)]
    lines += [f"export const w{i} = 1;" for i in range(90)]
    config = scaffold(tmp_path, {"src/a.ts": "\n".join(lines) + "\n"})
    assert config["printWidth"] == 100


def test_dependencies_are_not_read_as_the_repo_style(tmp_path):
    files = {"src/a.ts": SEMI_DOUBLE_2, "node_modules/x/index.js": NO_SEMI_SINGLE_4 * 20}
    assert scaffold(tmp_path, files)["singleQuote"] is False


def test_repo_without_code_gets_prettier_defaults(tmp_path):
    assert scaffold(tmp_path, {"README.md": "# x\n"}) == {}


def test_existing_config_file_is_left_alone(tmp_path):
    out = run(repo(tmp_path, {".prettierrc.yaml": "semi: false\n", "src/a.ts": SEMI_DOUBLE_2}))
    assert not (tmp_path / ".prettierrc.json").exists()
    assert "skip (Prettier already configured)" in out


def test_package_json_prettier_key_counts_as_config(tmp_path):
    pkg = json.dumps({"name": "x", "prettier": {"semi": False}})
    run(repo(tmp_path, {"package.json": pkg, "src/a.ts": SEMI_DOUBLE_2}))
    assert not (tmp_path / ".prettierrc.json").exists()


def test_interface_members_do_not_read_as_missing_trailing_commas(tmp_path):
    # TS interface members end in `;`, never a comma, under every trailingComma setting.
    iface = "\n".join(f"interface I{i} {{\n  a: string;\n  b: number;\n}}" for i in range(20))
    config = scaffold(tmp_path, {"src/a.ts": iface + "\n" + SEMI_DOUBLE_2})
    assert config["trailingComma"] != "none"


def test_code_without_trailing_commas_means_none(tmp_path):
    code = SEMI_DOUBLE_2.replace("size: x,", "size: x")
    config = scaffold(tmp_path, {"src/a.ts": code})
    assert config["trailingComma"] == "none"
    assert "overrides" not in config


def test_tracked_file_deleted_from_the_worktree_is_skipped(tmp_path):
    repo(tmp_path, {"src/a.ts": SEMI_DOUBLE_2, "src/gone.ts": SEMI_DOUBLE_2})
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    (tmp_path / "src" / "gone.ts").unlink()
    run(tmp_path)
    assert (tmp_path / ".prettierrc.json").exists()


def test_config_at_the_repo_root_covers_a_package_below_it(tmp_path):
    # Prettier resolves configs upward, so a package config here would override the root's.
    repo(tmp_path, {".prettierrc": "{}\n", "packages/web/src/a.ts": SEMI_DOUBLE_2})
    run(tmp_path, "packages/web")
    assert not (tmp_path / "packages" / "web" / ".prettierrc.json").exists()


def test_package_below_the_root_is_read_from_its_own_files(tmp_path):
    repo(tmp_path, {"packages/web/src/a.js": NO_SEMI_SINGLE_4, "other/b.ts": SEMI_DOUBLE_2 * 20})
    run(tmp_path, "packages/web")
    config = json.loads((tmp_path / "packages" / "web" / ".prettierrc.json").read_text(encoding="utf-8"))
    assert config["semi"] is False

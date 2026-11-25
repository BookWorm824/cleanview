"""Every name the shipped code reads from another of its modules is there (1.18.171,
2026-11-25; her "CleanView couldn't check" note for Pretty Woman on 1.18.170: "AttributeError:
module 'cvcore' has no attribute 'LANG'"). 1.18.133 wrote `cl.LANG` (cvcore) for `cvlang.LANG`
in analyze's check for a lone "God," when no subtitles lined up, so every video with God's name
ticked and no subtitles used failed the whole scan; the tests called `heard_bare_god` directly
and never reached that line. This reads each shipped file and checks every `alias.name` it
reads against the module itself."""
import ast
import importlib
import json
import unittest

import support  # noqa: F401  (must come first)

ROOT = support.ROOT


def shipped_code():
    with open(ROOT / "version.json", encoding="utf8") as f:
        files = json.load(f)["files"]
    return [n for n in files if n.endswith((".py", ".pyw"))]


def module_aliases(tree, ours):
    """{alias: module name} for `import x` / `import x as y` of our own modules."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in ours:
                    out[a.asname or a.name] = a.name
    return out


def set_from_outside(trees, ours):
    """Names some file sets on one of our modules (`cc.MODEL = ...`): they exist once run."""
    made = set()
    for tree in trees:
        al = module_aliases(tree, ours)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                    and isinstance(node.value, ast.Name) and node.value.id in al:
                made.add((al[node.value.id], node.attr))
    return made


class ModuleNames(unittest.TestCase):

    def test_every_name_read_exists(self):
        names = shipped_code()
        ours = {n.rsplit(".", 1)[0] for n in names if n.endswith(".py")}
        trees = {}
        for n in names:
            with open(ROOT / n, encoding="utf8") as f:
                trees[n] = ast.parse(f.read(), n)
        made = set_from_outside(trees.values(), ours)
        mods = {}
        missing = []
        for n, tree in trees.items():
            al = module_aliases(tree, ours)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                        and isinstance(node.value, ast.Name) and node.value.id in al):
                    continue
                mod = al[node.value.id]
                if mod not in mods:
                    try:
                        mods[mod] = importlib.import_module(mod)
                    except Exception:           # a module this PC can't load: not checked
                        mods[mod] = None
                m = mods[mod]
                if m is None or hasattr(m, node.attr) or (mod, node.attr) in made:
                    continue
                missing.append(f"{n}:{node.lineno} {node.value.id}.{node.attr} "
                               f"({mod} has no {node.attr})")
        self.assertEqual(missing, [])

    def test_the_line_from_her_note(self):
        import cleanview as engine
        import cvlang
        with open(ROOT / "cleanview.py", encoding="utf8") as f:
            src = f.read()
        self.assertFalse("cl.LANG" in src)
        self.assertIn('"deity" in cats and not cues and cvlang.LANG == "en"', src)
        self.assertEqual(cvlang.LANG, "en")
        self.assertTrue(callable(engine.heard_bare_god))


if __name__ == "__main__":
    unittest.main()

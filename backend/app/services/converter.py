from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..models import Selection

TAG_MAP = {
    "div": "View",
    "span": "Text",
    "p": "Text",
    "img": "Image",
    "ul": "View",
    "ol": "View",
    "li": "Text",
    "section": "View",
    "header": "View",
    "footer": "View",
    "main": "View",
    "nav": "View",
    "button": "Pressable",
    "a": "Pressable",
    "form": "View",
    "label": "Text",
    "input": "TextInput",
    "textarea": "TextInput",
    "h1": "Text",
    "h2": "Text",
    "h3": "Text",
    "h4": "Text",
    "h5": "Text",
    "h6": "Text",
    "table": "View",
    "thead": "View",
    "tbody": "View",
    "tr": "View",
    "td": "Text",
    "th": "Text",
}

BASE_RN_IMPORTS = {"View", "Text", "Image", "ScrollView", "Pressable"}

EXTRA_DEP_VERSIONS = {
    "nativewind": "^4.0.38",
    "tailwindcss": "^3.4.10",
    "react-native-svg": "^15.3.0",
    "styled-components": "^6.1.12",
    "@emotion/native": "^11.11.3",
    "react-native-document-picker": "^9.3.0",
    "moti": "^0.27.0",
    "react-native-reanimated": "^3.10.0",
}

IMPORT_REWRITES = {
    "styled-components": "styled-components/native",
    "@emotion/styled": "@emotion/native",
}

WEB_ONLY_LIBS = {
    "react-router-dom": "Use @react-navigation/native",
    "react-router": "Use @react-navigation/native",
    "@mui/material": "No direct RN equivalent; consider react-native-paper",
    "antd": "No direct RN equivalent; consider react-native-paper",
    "react-bootstrap": "No direct RN equivalent; use RN components",
    "bootstrap": "No direct RN equivalent; use RN styles",
    "react-icons": "Use react-native-vector-icons",
    "react-toastify": "Use react-native-toast-message",
    "react-hot-toast": "Use react-native-toast-message",
}

STYLED_TAG_MAP = {
    "div": "View",
    "span": "Text",
    "p": "Text",
    "img": "Image",
    "button": "Pressable",
    "a": "Text",
    "section": "View",
    "header": "View",
    "footer": "View",
    "main": "View",
    "nav": "View",
    "ul": "View",
    "ol": "View",
    "li": "Text",
    "input": "TextInput",
    "textarea": "TextInput",
    "h1": "Text",
    "h2": "Text",
    "h3": "Text",
    "h4": "Text",
    "h5": "Text",
    "h6": "Text",
}

CSS_PROP_MAP = {
    "background": "backgroundColor",
    "background-color": "backgroundColor",
    "color": "color",
    "font-size": "fontSize",
    "font-weight": "fontWeight",
    "font-style": "fontStyle",
    "line-height": "lineHeight",
    "letter-spacing": "letterSpacing",
    "text-align": "textAlign",
    "text-transform": "textTransform",
    "opacity": "opacity",
    "width": "width",
    "height": "height",
    "min-width": "minWidth",
    "max-width": "maxWidth",
    "min-height": "minHeight",
    "max-height": "maxHeight",
    "display": "display",
    "flex": "flex",
    "flex-direction": "flexDirection",
    "flex-wrap": "flexWrap",
    "align-items": "alignItems",
    "justify-content": "justifyContent",
    "align-self": "alignSelf",
    "gap": "gap",
    "row-gap": "rowGap",
    "column-gap": "columnGap",
    "border-radius": "borderRadius",
    "border-color": "borderColor",
    "border-style": "borderStyle",
    "border-width": "borderWidth",
    "position": "position",
    "top": "top",
    "right": "right",
    "bottom": "bottom",
    "left": "left",
    "overflow": "overflow",
    "z-index": "zIndex",
}


@dataclass
class ConvertResult:
    total_files: int
    converted_files: int
    issues: list[str]
    warnings: list[str]
    output_dir: Path


@dataclass
class ConversionOptions:
    use_nativewind: bool


@dataclass
class ConversionOutcome:
    text: str
    issues: list[str]
    warnings: list[str]
    dependencies: set[str]


@dataclass
class CssImport:
    path: str
    default_name: str | None
    is_module: bool
    is_side_effect: bool


@dataclass
class CssMapsResult:
    module_maps: dict[str, dict[str, dict[str, object]]]
    global_map: dict[str, dict[str, object]]
    global_name: str
    warnings: list[str]


def convert_project(source_dir: Path, output_dir: Path, selection: Selection) -> ConvertResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_root = output_dir / "react-native"
    out_root.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    issues: list[str] = []
    extra_dependencies: set[str] = set()

    style_choice = (selection.styles or "").lower()
    options = ConversionOptions(use_nativewind=("tailwind" in style_choice or "nativewind" in style_choice))
    payment_integrations = _detect_payment_integrations(source_dir)

    frontend_root = _find_frontend_root(source_dir)
    if frontend_root is None:
        warnings.append("No frontend root found. Placeholder app created.")
        _write_placeholder_app(out_root)
        if payment_integrations:
            _write_payment_stubs(out_root, payment_integrations)
            _write_payment_native_scaffolds(out_root, payment_integrations)
        _write_package_json(out_root, extra_dependencies)
        _write_readme(out_root, selection, extra_dependencies, options.use_nativewind, payment_integrations)
        return ConvertResult(0, 0, issues, warnings, out_root)

    src_dir = _find_src_dir(frontend_root)
    jsx_files = list(src_dir.rglob("*.jsx")) + list(src_dir.rglob("*.tsx"))

    converted_root = out_root / "src" / "converted"
    converted_root.mkdir(parents=True, exist_ok=True)

    total_files = len(jsx_files)
    converted_files = 0

    for file_path in jsx_files:
        original = file_path.read_text(encoding="utf-8", errors="ignore")
        outcome = _convert_jsx_text(original, file_path, options)
        if outcome.issues:
            issues.extend([f"{file_path.name}: {issue}" for issue in outcome.issues])
        if outcome.warnings:
            warnings.extend([f"{file_path.name}: {warning}" for warning in outcome.warnings])
        extra_dependencies.update(outcome.dependencies)

        relative_path = file_path.relative_to(src_dir)
        output_path = converted_root / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(outcome.text, encoding="utf-8")
        converted_files += 1

    _write_placeholder_app(out_root)
    if payment_integrations:
        _write_payment_stubs(out_root, payment_integrations)
        _write_payment_native_scaffolds(out_root, payment_integrations)
    _write_package_json(out_root, extra_dependencies)
    if options.use_nativewind:
        _write_nativewind_config(out_root)
    _write_readme(out_root, selection, extra_dependencies, options.use_nativewind, payment_integrations)

    if total_files == 0:
        warnings.append("No JSX/TSX files found to convert.")

    return ConvertResult(total_files, converted_files, issues, warnings, out_root)


def _find_frontend_root(source_dir: Path) -> Path | None:
    for package_json in source_dir.rglob("package.json"):
        try:
            text = package_json.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if '"react"' in text:
            return package_json.parent
    return None


def _find_src_dir(frontend_root: Path) -> Path:
    src_dir = frontend_root / "src"
    return src_dir if src_dir.exists() else frontend_root


def _convert_jsx_text(text: str, file_path: Path, options: ConversionOptions) -> ConversionOutcome:
    issues: list[str] = []
    warnings: list[str] = []
    dependencies: set[str] = set()
    rn_imports = set(BASE_RN_IMPORTS)
    style_objects: dict[str, dict[str, dict[str, object]]] = {}
    class_usage: dict[str, set[str]] = {}
    needs_stylesheet = False

    text = _rewrite_imports(text, issues, warnings, dependencies)
    text = _rewrite_next_imports(text)
    text, moti_imports, moti_deps = _rewrite_framer_motion(text)
    if moti_imports:
        dependencies.update(moti_deps)
        text = _ensure_named_import(text, "moti", moti_imports)
    _detect_web_only_libs(text, warnings)

    text = _rewrite_styled_tags(text, warnings)

    text, css_imports = _extract_css_imports(text)
    css_result = _load_css_maps(file_path, css_imports)
    if css_result.warnings:
        warnings.extend(css_result.warnings)

    # Form and table tags are converted to View; follow-up may be needed.

    if re.search(r"<\s*textarea\b", text):
        rn_imports.add("TextInput")
        text = re.sub(r"<\s*textarea\b", "<TextInput multiline", text)
        text = re.sub(r"</\s*textarea\s*>", "</TextInput>", text)

    if re.search(r"<\s*input\b", text):
        rn_imports.add("TextInput")

    if "className=" in text:
        if options.use_nativewind:
            dependencies.update({"nativewind", "tailwindcss"})
        else:
            text, module_usage, module_issues = _convert_classname_modules(text)
            issues.extend(module_issues)
            class_usage.update(module_usage)

            text, string_usage, string_issues = _convert_classname_strings(text, css_result)
            issues.extend(string_issues)
            if string_usage:
                class_usage.setdefault(css_result.global_name, set()).update(string_usage)

            if "className=" in text:
                issues.append("className expressions need manual style mapping")
                text = text.replace("className=", "style=")

            needs_stylesheet = True
            rn_imports.add("StyleSheet")

    if css_imports and not needs_stylesheet and not options.use_nativewind:
        warnings.append("Stylesheets imported but no className usage mapped")

    if "onClick=" in text:
        text = text.replace("onClick=", "onPress=")

    doc_picker_needed = False

    text, custom_imports, custom_deps, custom_needs_picker = _rewrite_custom_input_components(text)
    if custom_imports:
        rn_imports.update(custom_imports)
    if custom_deps:
        dependencies.update(custom_deps)
    if custom_needs_picker:
        doc_picker_needed = True

    text, input_imports, input_deps, input_needs_picker = _rewrite_input_tags(text)
    if input_imports:
        rn_imports.update(input_imports)
    if input_deps:
        dependencies.update(input_deps)
    if input_needs_picker:
        doc_picker_needed = True

    text = _rewrite_link_tags(text)
    text, _ = _rewrite_href_attributes(text, rn_imports)

    text, img_warnings = _rewrite_img_sources(text)
    if img_warnings:
        warnings.extend(img_warnings)

    text = re.sub(r"alt\s*=\s*\"([^\"]+)\"", r"accessibilityLabel=\"\1\"", text)
    text = re.sub(r"(<TextInput[^>]*?)\sonChange=", r"\1 onChangeText=", text)

    text, type_warnings = _map_input_types(text)
    warnings.extend(type_warnings)

    for html_tag, rn_tag in TAG_MAP.items():
        text = re.sub(rf"<\s*{html_tag}\b", f"<{rn_tag}", text)
        text = re.sub(rf"</\s*{html_tag}\s*>", f"</{rn_tag}>", text)

    if needs_stylesheet:
        style_objects.update(_build_style_objects(css_result, class_usage))
        if style_objects:
            text = _append_style_objects(text, style_objects)

    if doc_picker_needed:
        dependencies.add("react-native-document-picker")
        text = _ensure_default_import(text, "DocumentPicker", "react-native-document-picker")

    text = _upsert_react_native_imports(text, rn_imports)

    if warnings:
        warnings = list(dict.fromkeys(warnings))

    return ConversionOutcome(text=text, issues=issues, warnings=warnings, dependencies=dependencies)


def _write_placeholder_app(out_root: Path) -> None:
    app_path = out_root / "App.tsx"
    app_path.write_text(
        "import React from \"react\";\n"
        "import { View, Text } from \"react-native\";\n\n"
        "export default function App() {\n"
        "  return (\n"
        "    <View style={{ flex: 1, padding: 24, justifyContent: \"center\" }}>\n"
        "      <Text>Conversion output generated. Review src/converted.</Text>\n"
        "    </View>\n"
        "  );\n"
        "}\n",
        encoding="utf-8",
    )


def _write_package_json(out_root: Path, extra_dependencies: set[str] | None = None) -> None:
    package_json = out_root / "package.json"
    deps = {
        "react": "^18.3.1",
        "react-native": "0.75.0",
    }

    for dep in sorted(extra_dependencies or set()):
        if dep not in deps:
            deps[dep] = EXTRA_DEP_VERSIONS.get(dep, "latest")

    package = {
        "name": "react-native-output",
        "private": True,
        "version": "0.1.0",
        "main": "index.js",
        "dependencies": deps,
    }

    package_json.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")

    index_js = out_root / "index.js"
    index_js.write_text(
        "import { AppRegistry } from \"react-native\";\n"
        "import App from \"./App\";\n"
        "import { name as appName } from \"./app.json\";\n\n"
        "AppRegistry.registerComponent(appName, () => App);\n",
        encoding="utf-8",
    )

    app_json = out_root / "app.json"
    app_json.write_text(
        "{\n"
        "  \"name\": \"ReactNativeOutput\",\n"
        "  \"displayName\": \"React Native Output\"\n"
        "}\n",
        encoding="utf-8",
    )


def _write_readme(
    out_root: Path,
    selection: Selection,
    extra_dependencies: set[str],
    use_nativewind: bool,
    payments: list[str],
) -> None:
    readme = out_root / "README_CONVERSION.md"
    lines = [
        "Conversion output generated by the analyzer.",
        "",
        "Selections used:",
        f"- frontend: {selection.frontend or 'unknown'}",
        f"- backend: {selection.backend or 'unknown'}",
        f"- database: {selection.database or 'unknown'}",
        f"- styles: {selection.styles or 'unknown'}",
        "",
    ]

    if extra_dependencies:
        lines.append("Extra dependencies detected:")
        for dep in sorted(extra_dependencies):
            lines.append(f"- {dep}")
        lines.append("")

    if use_nativewind:
        lines.append("NativeWind config files were generated for className support.")
        lines.append("")

    if payments:
        lines.append("Payment stubs generated:")
        for name in payments:
            lines.append(f"- {name} (native SDK placeholder)")
        lines.append("")
        lines.append("Native module scaffolds generated under native/.")
        lines.append("")

    lines.extend(
        [
            "Next steps:",
            "- Install dependencies in this folder.",
            "- Review src/converted for JSX to RN mapping fixes.",
            "- Replace placeholder App.tsx with your entry screen.",
            "- Update payment checkout URLs in src/payments.",
            "- Follow native/README_NATIVE.md to wire Android/iOS SDKs.",
            "",
        ]
    )

    readme.write_text("\n".join(lines), encoding="utf-8")


def _write_nativewind_config(out_root: Path) -> None:
    (out_root / "tailwind.config.js").write_text(
        "module.exports = {\n"
        "  content: [\n"
        "    \"./App.{js,jsx,ts,tsx}\",\n"
        "    \"./src/**/*.{js,jsx,ts,tsx}\",\n"
        "  ],\n"
        "  theme: { extend: {} },\n"
        "  plugins: [],\n"
        "};\n",
        encoding="utf-8",
    )

    (out_root / "babel.config.js").write_text(
        "module.exports = function (api) {\n"
        "  api.cache(true);\n"
        "  return {\n"
        "    presets: [\"module:metro-react-native-babel-preset\"],\n"
        "    plugins: [\"nativewind/babel\"],\n"
        "  };\n"
        "};\n",
        encoding="utf-8",
    )

    (out_root / "nativewind-env.d.ts").write_text(
        "/// <reference types=\"nativewind/types\" />\n",
        encoding="utf-8",
    )


def _extract_css_imports(text: str) -> tuple[str, list[CssImport]]:
    imports: list[CssImport] = []

    def replace_default(match: re.Match[str]) -> str:
        default_name = match.group(1)
        path = match.group(2)
        imports.append(
            CssImport(
                path=path,
                default_name=default_name,
                is_module=".module." in path,
                is_side_effect=False,
            )
        )
        return ""

    def replace_side_effect(match: re.Match[str]) -> str:
        path = match.group(1)
        imports.append(
            CssImport(
                path=path,
                default_name=None,
                is_module=".module." in path,
                is_side_effect=True,
            )
        )
        return ""

    text = re.sub(
        r'^\s*import\s+([A-Za-z_$][\w$]*)\s+from\s+["\']([^"\']+\.(?:css|scss|sass))["\'];?\s*$',
        replace_default,
        text,
        flags=re.MULTILINE,
    )

    text = re.sub(
        r'^\s*import\s+["\']([^"\']+\.(?:css|scss|sass))["\'];?\s*$',
        replace_side_effect,
        text,
        flags=re.MULTILINE,
    )

    return text, imports


def _load_css_maps(file_path: Path, css_imports: list[CssImport]) -> CssMapsResult:
    module_maps: dict[str, dict[str, dict[str, object]]] = {}
    global_map: dict[str, dict[str, object]] = {}
    warnings: list[str] = []
    global_name = "globalStyles"

    for css_import in css_imports:
        if not css_import.path.startswith("."):
            warnings.append(f"External stylesheet skipped: {css_import.path}")
            continue

        css_path = (file_path.parent / css_import.path).resolve()
        if not css_path.exists():
            warnings.append(f"Stylesheet not found: {css_import.path}")
            continue

        styles, css_warnings = _parse_css_file(css_path)
        if css_warnings:
            warnings.extend(css_warnings)

        if css_import.default_name:
            module_maps[css_import.default_name] = styles
        else:
            for key, value in styles.items():
                global_map.setdefault(key, {}).update(value)

    return CssMapsResult(
        module_maps=module_maps,
        global_map=global_map,
        global_name=global_name,
        warnings=warnings,
    )


def _convert_classname_modules(text: str) -> tuple[str, dict[str, set[str]], list[str]]:
    issues: list[str] = []
    usage: dict[str, set[str]] = {}

    def dot_repl(match: re.Match[str]) -> str:
        name = match.group(1)
        cls = match.group(2)
        usage.setdefault(name, set()).add(cls)
        return f"style={{{name}.{cls}}}"

    def bracket_repl(match: re.Match[str]) -> str:
        name = match.group(1)
        cls = match.group(2)
        usage.setdefault(name, set()).add(cls)
        return f"style={{{name}['{cls}']}}"

    text = re.sub(r"className\s*=\s*{([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)}", dot_repl, text)
    text = re.sub(
        r"className\s*=\s*{([A-Za-z_$][\w$]*)\[['\"]([^'\"]+)['\"]]}",
        bracket_repl,
        text,
    )

    return text, usage, issues


def _convert_classname_strings(
    text: str, css_result: CssMapsResult
) -> tuple[str, set[str], list[str]]:
    issues: list[str] = []
    used: set[str] = set()

    def repl(match: re.Match[str]) -> str:
        names = match.group(1).split()
        for name in names:
            used.add(name)

        if not names:
            return ""

        styles_name = css_result.global_name
        if len(names) == 1:
            return f'style={{{styles_name}["{names[0]}"]}}'
        joined = ", ".join([f'{styles_name}["{name}"]' for name in names])
        return f"style={{[{joined}]}}"

    text = re.sub(r'className\s*=\s*"([^"]+)"', repl, text)
    text = re.sub(r"className\s*=\s*'([^']+)'", repl, text)

    if used and not css_result.global_map:
        issues.append("string className mapped to generated styles; verify CSS coverage")

    return text, used, issues


def _build_style_objects(
    css_result: CssMapsResult, class_usage: dict[str, set[str]]
) -> dict[str, dict[str, dict[str, object]]]:
    objects: dict[str, dict[str, dict[str, object]]] = {}

    for name, style_map in css_result.module_maps.items():
        used = class_usage.get(name, set())
        objects[name] = _filter_style_map(style_map, used)

    global_used = class_usage.get(css_result.global_name, set())
    if css_result.global_map or global_used:
        objects[css_result.global_name] = _filter_style_map(css_result.global_map, global_used)

    return objects


def _filter_style_map(
    style_map: dict[str, dict[str, object]], used: set[str]
) -> dict[str, dict[str, object]]:
    if not used:
        return style_map
    return {name: style_map.get(name, {}) for name in sorted(used)}


def _append_style_objects(
    text: str, style_objects: dict[str, dict[str, dict[str, object]]]
) -> str:
    for name, styles in style_objects.items():
        if not styles:
            continue
        if re.search(rf"\bconst\s+{re.escape(name)}\s*=", text):
            continue

        payload = json.dumps(styles, indent=2)
        text += f"\n\nconst {name} = StyleSheet.create({payload});\n"
    return text


def _parse_css_file(css_path: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    text = css_path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    warnings: list[str] = []
    styles: dict[str, dict[str, object]] = {}
    unsupported: set[str] = set()
    variables: dict[str, str] = {}
    missing_vars: set[str] = set()

    for match in re.finditer(r"([^{}]+)\{([^{}]+)\}", text):
        selectors = match.group(1)
        body = match.group(2)
        for selector in selectors.split(","):
            selector = selector.strip()
            class_name = _selector_to_class(selector)
            if not class_name:
                continue

            declarations, props_unsupported = _parse_css_block(body, variables, missing_vars)
            if props_unsupported:
                unsupported.update(props_unsupported)

            if declarations:
                styles.setdefault(class_name, {}).update(declarations)

    if unsupported:
        warnings.append(
            "Unsupported CSS properties skipped: " + ", ".join(sorted(unsupported))
        )

    if missing_vars:
        warnings.append(
            "Unresolved CSS variables: " + ", ".join(sorted(missing_vars))
        )

    return styles, warnings


def _selector_to_class(selector: str) -> str | None:
    if selector.startswith("@"):
        return None
    if " " in selector or ">" in selector or "+" in selector or "~" in selector:
        return None
    if not selector.startswith("."):
        return None

    selector = selector[1:]
    selector = selector.split(":", 1)[0]
    selector = selector.split("[", 1)[0]
    if not selector:
        return None
    return selector


def _parse_css_block(
    block: str,
    variables: dict[str, str],
    missing_vars: set[str],
) -> tuple[dict[str, object], set[str]]:
    styles: dict[str, object] = {}
    unsupported: set[str] = set()

    for decl in block.split(";"):
        if ":" not in decl:
            continue
        prop, raw_value = decl.split(":", 1)
        prop = prop.strip().lower()
        value = raw_value.strip().replace("!important", "").strip()
        if not prop or not value:
            continue

        if prop.startswith("--"):
            variables[prop] = value
            continue

        value = _resolve_css_var(value, variables, missing_vars)

        if prop in ("margin", "padding"):
            styles.update(_expand_box_values(prop, value))
            continue

        if prop == "border":
            styles.update(_parse_border_shorthand(value))
            continue

        mapped = CSS_PROP_MAP.get(prop)
        if not mapped:
            unsupported.add(prop)
            continue

        styles[mapped] = _parse_css_value(value)

    return styles, unsupported


def _expand_box_values(prop: str, value: str) -> dict[str, object]:
    parts = value.split()
    if not parts:
        return {}

    values = [_parse_css_value(part) for part in parts]
    if len(values) == 1:
        return {prop: values[0]}
    if len(values) == 2:
        return {f"{prop}Vertical": values[0], f"{prop}Horizontal": values[1]}
    if len(values) == 3:
        return {
            f"{prop}Top": values[0],
            f"{prop}Horizontal": values[1],
            f"{prop}Bottom": values[2],
        }
    if len(values) >= 4:
        return {
            f"{prop}Top": values[0],
            f"{prop}Right": values[1],
            f"{prop}Bottom": values[2],
            f"{prop}Left": values[3],
        }
    return {}


def _parse_border_shorthand(value: str) -> dict[str, object]:
    parts = value.split()
    styles: dict[str, object] = {}
    for part in parts:
        if part.endswith("px") or part.isdigit():
            styles["borderWidth"] = _parse_css_value(part)
            continue
        if part in {"solid", "dashed", "dotted"}:
            styles["borderStyle"] = part
            continue
        styles["borderColor"] = part
    return styles


def _parse_css_value(value: str) -> object:
    if value.endswith("px"):
        return _parse_number(value[:-2])
    if value.endswith("rem"):
        return _parse_number(value[:-3]) * 16
    if value.endswith("em"):
        return _parse_number(value[:-2]) * 16
    if value.isdigit():
        return int(value)
    if _is_number(value):
        return float(value)
    return value


def _resolve_css_var(
    value: str, variables: dict[str, str], missing_vars: set[str]
) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        fallback = match.group(2)
        if name in variables:
            return variables[name]
        if fallback:
            return fallback.strip()
        missing_vars.add(name)
        return match.group(0)

    return re.sub(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^\)]+))?\)", repl, value)


def _parse_number(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _rewrite_styled_tags(text: str, warnings: list[str]) -> str:
    for html_tag, rn_tag in STYLED_TAG_MAP.items():
        if re.search(rf"styled\.{html_tag}\b", text):
            warnings.append(f"styled.{html_tag} converted to styled.{rn_tag}")
        text = re.sub(rf"styled\.{html_tag}\b", f"styled.{rn_tag}", text)
        text = re.sub(
            rf"styled\(\s*[\"\']{html_tag}[\"\']\s*\)",
            f"styled('{rn_tag}')",
            text,
        )
    return text


def _rewrite_next_imports(text: str) -> str:
    patterns = [
        r'^\s*import\s+Link\s+from\s+["\']next/link["\'];?\s*$',
        r'^\s*import\s+Image\s+from\s+["\']next/image["\'];?\s*$',
        r'^\s*import\s+\{[^}]+\}\s+from\s+["\']next["\'];?\s*$',
        r'^\s*import\s+[^\s]+\s+from\s+["\']next["\'];?\s*$',
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)
    return text


def _rewrite_link_tags(text: str) -> str:
    text = re.sub(r"<\s*Link\b", "<Pressable", text)
    text = re.sub(r"</\s*Link\s*>", "</Pressable>", text)
    return text


def _rewrite_framer_motion(text: str) -> tuple[str, set[str], set[str]]:
    if "framer-motion" not in text and "motion." not in text:
        return text, set(), set()

    text = re.sub(
        r'^\s*import\s+\{[^}]*\}\s+from\s+["\']framer-motion["\'];?\s*$',
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r'^\s*import\s+[^\s]+\s+from\s+["\']framer-motion["\'];?\s*$',
        "",
        text,
        flags=re.MULTILINE,
    )

    moti_imports: set[str] = set()
    text_tags = {"span", "p", "h1", "h2", "h3", "h4", "h5", "h6", "label"}

    def repl(match: re.Match[str]) -> str:
        tag = match.group(1)
        if tag in text_tags:
            moti_imports.add("MotiText")
            return "MotiText"
        moti_imports.add("MotiView")
        return "MotiView"

    text = re.sub(r"\bmotion\.([a-zA-Z][\w-]*)", repl, text)
    return text, moti_imports, {"moti", "react-native-reanimated"}


def _ensure_default_import(text: str, name: str, module: str) -> str:
    if re.search(rf'import\s+{re.escape(name)}\s+from\s+["\']{re.escape(module)}["\']', text):
        return text

    import_line = f'import {name} from "{module}";'
    if "import React" in text:
        return import_line + "\n" + text
    return import_line + "\n" + text


def _ensure_named_import(text: str, module: str, names: set[str]) -> str:
    if not names:
        return text

    match = re.search(
        rf'import\s+\{{([^}}]+)\}}\s+from\s+["\']{re.escape(module)}["\'];',
        text,
    )
    if match:
        existing = {item.strip() for item in match.group(1).split(",") if item.strip()}
        combined = sorted(existing | names)
        new_import = f'import {{{", ".join(combined)}}} from "{module}";'
        return text[: match.start()] + new_import + text[match.end() :]

    import_line = f'import {{{", ".join(sorted(names))}}} from "{module}";'
    if "import React" in text:
        return import_line + "\n" + text
    return import_line + "\n" + text


def _rewrite_href_attributes(text: str, rn_imports: set[str]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if "href=" not in text:
        return text, warnings

    rn_imports.add("Linking")

    def repl_string(match: re.Match[str]) -> str:
        value = match.group(1)
        if value.startswith("http://") or value.startswith("https://"):
            return f'onPress={{() => Linking.openURL("{value}")}}'
        if value.startswith("mailto:") or value.startswith("tel:"):
            return f'onPress={{() => Linking.openURL("{value}")}}'
        return f'onPress={{() => Linking.openURL("{value}")}}'

    def repl_expr(match: re.Match[str]) -> str:
        return f"onPress={{() => Linking.openURL({match.group(1)})}}"

    text = re.sub(r"href\s*=\s*\"([^\"]+)\"", repl_string, text)
    text = re.sub(r"href\s*=\s*{([^}]+)}", repl_expr, text)
    return text, warnings


def _rewrite_input_tags(text: str) -> tuple[str, set[str], set[str], bool]:
    imports: set[str] = set()
    dependencies: set[str] = set()
    needs_picker = False

    def get_attr(attrs: str, name: str) -> str | None:
        match = re.search(rf"\b{name}\s*=\s*\"([^\"]+)\"", attrs)
        if match:
            return match.group(1)
        match = re.search(rf"\b{name}\s*=\s*'([^']+)'", attrs)
        return match.group(1) if match else None

    def drop_attr(attrs: str, name: str) -> str:
        attrs = re.sub(rf"\s+{name}\s*=\s*\"[^\"]+\"", "", attrs)
        attrs = re.sub(rf"\s+{name}\s*=\s*'[^']+'", "", attrs)
        return attrs

    def replace_attr(attrs: str, name: str, new_name: str) -> str:
        return re.sub(rf"\b{name}\s*=", f"{new_name}=", attrs)

    def rewrite_input(match: re.Match[str]) -> str:
        nonlocal needs_picker
        attrs = match.group(1) or ""
        input_type = get_attr(attrs, "type")
        if not input_type:
            return match.group(0)

        input_type = input_type.lower()

        if input_type == "checkbox":
            imports.add("Switch")
            attrs = drop_attr(attrs, "type")
            attrs = replace_attr(attrs, "checked", "value")
            attrs = replace_attr(attrs, "onChange", "onValueChange")
            return f"<Switch{attrs} />"

        if input_type in {"submit", "button", "reset", "file", "color"}:
            imports.add("Button")
            attrs = drop_attr(attrs, "type")

            title = get_attr(attrs, "value")
            attrs = drop_attr(attrs, "value")
            attrs = drop_attr(attrs, "accept")
            if input_type == "file":
                attrs = drop_attr(attrs, "onChange")

            if not title:
                if input_type == "submit":
                    title = "Submit"
                elif input_type == "reset":
                    title = "Reset"
                elif input_type == "file":
                    title = "Select file"
                elif input_type == "color":
                    title = "Pick color"
                else:
                    title = "Button"

            if input_type == "file":
                dependencies.add("react-native-document-picker")
                needs_picker = True
                if "onPress=" not in attrs:
                    attrs += (
                        " onPress={async () => { try { await DocumentPicker.pickSingle({ type: [DocumentPicker.types.allFiles] }); } catch (err) {} }}"
                    )

            attrs = f" title=\"{title}\"" + attrs
            return f"<Button{attrs} />"

        return match.group(0)

    text = re.sub(r"<input([^>]*)/?>", rewrite_input, text)
    return text, imports, dependencies, needs_picker


def _rewrite_custom_input_components(text: str) -> tuple[str, set[str], set[str], bool]:
    imports: set[str] = set()
    dependencies: set[str] = set()
    needs_picker = False

    def get_attr(attrs: str, name: str) -> str | None:
        match = re.search(rf"\b{name}\s*=\s*\"([^\"]+)\"", attrs)
        if match:
            return match.group(1)
        match = re.search(rf"\b{name}\s*=\s*'([^']+)'", attrs)
        return match.group(1) if match else None

    def drop_attr(attrs: str, name: str) -> str:
        attrs = re.sub(rf"\s+{name}\s*=\s*\"[^\"]+\"", "", attrs)
        attrs = re.sub(rf"\s+{name}\s*=\s*'[^']+'", "", attrs)
        return attrs

    def replace_attr(attrs: str, name: str, new_name: str) -> str:
        return re.sub(rf"\b{name}\s*=", f"{new_name}=", attrs)

    def build_control(attrs: str) -> str:
        nonlocal needs_picker
        input_type = get_attr(attrs, "type")
        if input_type:
            input_type = input_type.lower()

        if input_type == "checkbox":
            imports.add("Switch")
            attrs = drop_attr(attrs, "type")
            attrs = replace_attr(attrs, "checked", "value")
            attrs = replace_attr(attrs, "onChange", "onValueChange")
            return f"<Switch{attrs} />"

        if input_type in {"submit", "button", "reset", "file", "color"}:
            imports.add("Button")
            attrs = drop_attr(attrs, "type")

            title = get_attr(attrs, "value")
            attrs = drop_attr(attrs, "value")
            attrs = drop_attr(attrs, "accept")
            if input_type == "file":
                attrs = drop_attr(attrs, "onChange")

            if not title:
                if input_type == "submit":
                    title = "Submit"
                elif input_type == "reset":
                    title = "Reset"
                elif input_type == "file":
                    title = "Select file"
                elif input_type == "color":
                    title = "Pick color"
                else:
                    title = "Button"

            if input_type == "file":
                dependencies.add("react-native-document-picker")
                needs_picker = True
                if "onPress=" not in attrs:
                    attrs += (
                        " onPress={async () => { try { await DocumentPicker.pickSingle({ type: [DocumentPicker.types.allFiles] }); } catch (err) {} }}"
                    )

            attrs = f" title=\"{title}\"" + attrs
            return f"<Button{attrs} />"

        imports.add("TextInput")
        attrs = drop_attr(attrs, "type")
        return f"<TextInput{attrs} />"

    def rewrite_input_self(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        return build_control(attrs)

    def rewrite_input_block(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        children = match.group(2) or ""
        control = build_control(attrs)
        return f"<View>{control}{children}</View>"

    def rewrite_textarea_self(match: re.Match[str]) -> str:
        imports.add("TextInput")
        attrs = match.group(1) or ""
        if "multiline" not in attrs:
            attrs = " multiline" + attrs
        return f"<TextInput{attrs} />"

    def rewrite_textarea_block(match: re.Match[str]) -> str:
        imports.add("TextInput")
        attrs = match.group(1) or ""
        children = match.group(2) or ""
        if "multiline" not in attrs:
            attrs = " multiline" + attrs
        return f"<View><TextInput{attrs} />{children}</View>"

    text = re.sub(r"<Input([^>]*)/>", rewrite_input_self, text)
    text = re.sub(r"<Input([^>]*)>([\s\S]*?)</Input>", rewrite_input_block, text)
    text = re.sub(r"<Textarea([^>]*)/>", rewrite_textarea_self, text)
    text = re.sub(r"<TextArea([^>]*)/>", rewrite_textarea_self, text)
    text = re.sub(r"<Textarea([^>]*)>([\s\S]*?)</Textarea>", rewrite_textarea_block, text)
    text = re.sub(r"<TextArea([^>]*)>([\s\S]*?)</TextArea>", rewrite_textarea_block, text)

    return text, imports, dependencies, needs_picker


def _rewrite_img_sources(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []

    def repl_string(match: re.Match[str]) -> str:
        value = match.group(1)
        if value.startswith("http://") or value.startswith("https://"):
            return f'source={{ uri: "{value}" }}'
        if value.startswith("/"):
            return f'source={{require(".{value}")}}'
        if value.startswith("./") or value.startswith("../"):
            return f'source={{require("{value}")}}'
        return f'source={{ uri: "{value}" }}'

    def repl_expr(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        if "require(" in expr or "uri" in expr:
            return f"source={{{expr}}}"
        return f"source={{ uri: {expr} }}"

    text = re.sub(r"src\s*=\s*\"([^\"]+)\"", repl_string, text)
    text = re.sub(r"src\s*=\s*{([^}]+)}", repl_expr, text)
    return text, warnings


def _map_input_types(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    mapping = {
        "password": "secureTextEntry",
        "email": "keyboardType=\"email-address\"",
        "number": "keyboardType=\"numeric\"",
        "tel": "keyboardType=\"phone-pad\"",
        "url": "keyboardType=\"url\"",
    }
    silent = {"text", "search", "submit", "color"}

    def repl(match: re.Match[str]) -> str:
        value = match.group(1).lower()
        if value in silent:
            return ""
        replacement = mapping.get(value)
        if replacement:
            return " " + replacement
        warnings.append(f"input type '{value}' requires manual mapping")
        return ""

    text = re.sub(r"\s+type\s*=\s*\"([^\"]+)\"", repl, text)
    text = re.sub(r"\s+type\s*=\s*'([^']+)'", repl, text)
    return text, warnings


def _upsert_react_native_imports(text: str, rn_imports: set[str]) -> str:
    if not rn_imports:
        return text

    match = re.search(r'import\s+\{([^}]+)\}\s+from\s+["\']react-native["\'];', text)
    if match:
        existing = {item.strip() for item in match.group(1).split(",") if item.strip()}
        combined = sorted(existing | rn_imports)
        new_import = f'import {{{", ".join(combined)}}} from "react-native";'
        text = text[: match.start()] + new_import + text[match.end() :]
    else:
        import_line = f'import {{{", ".join(sorted(rn_imports))}}} from "react-native";'
        if 'import React' in text:
            text = import_line + "\n" + text
        else:
            text = "import React from \"react\";\n" + import_line + "\n" + text

    return text


def _rewrite_imports(
    text: str,
    issues: list[str],
    warnings: list[str],
    dependencies: set[str],
) -> str:
    for source, target in IMPORT_REWRITES.items():
        pattern = rf'from\s+["\']{re.escape(source)}["\']'
        text, count = re.subn(pattern, f'from "{target}"', text)
        if count:
            warnings.append(f"Rewrote import {source} -> {target}")
            if source == "styled-components":
                dependencies.add("styled-components")
            if source == "@emotion/styled":
                dependencies.add("@emotion/native")
    return text


def _detect_web_only_libs(text: str, warnings: list[str]) -> None:
    for module in _extract_import_modules(text):
        if module.startswith("react-icons"):
            warnings.append("react-icons is web-only; use react-native-vector-icons")
            continue

        if module in WEB_ONLY_LIBS:
            warnings.append(f"{module}: {WEB_ONLY_LIBS[module]}")


def _detect_payment_integrations(source_dir: Path) -> list[str]:
    results: set[str] = set()
    keywords = {
        "iyzico": "Iyzico",
        "iyzipay": "Iyzico",
        "dodopay": "DodoPayments",
        "dodo payments": "DodoPayments",
        "dodo-payments": "DodoPayments",
    }

    for package_json in source_dir.rglob("package.json"):
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            deps = data.get(section, {})
            if not isinstance(deps, dict):
                continue
            for dep in deps.keys():
                name = dep.lower()
                for key, label in keywords.items():
                    if key in name:
                        results.add(label)

    extensions = (".js", ".jsx", ".ts", ".tsx", ".env")
    files: list[Path] = []
    for ext in extensions:
        files.extend(source_dir.rglob(f"*{ext}"))

    for path in files[:300]:
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        for key, label in keywords.items():
            if key in text:
                results.add(label)

    return sorted(results)


def _write_payment_stubs(out_root: Path, payments: list[str]) -> None:
    payments_dir = out_root / "src" / "payments"
    payments_dir.mkdir(parents=True, exist_ok=True)

    if "Iyzico" in payments:
        _write_payment_stub(
            payments_dir / "IyzicoCheckout.tsx",
            name="Iyzico",
        )

    if "DodoPayments" in payments:
        _write_payment_stub(
            payments_dir / "DodoPaymentsCheckout.tsx",
            name="DodoPayments",
        )

    index_path = payments_dir / "index.ts"
    exports: list[str] = []
    if (payments_dir / "IyzicoCheckout.tsx").exists():
        exports.append("export { default as IyzicoCheckout } from './IyzicoCheckout';")
    if (payments_dir / "DodoPaymentsCheckout.tsx").exists():
        exports.append(
            "export { default as DodoPaymentsCheckout } from './DodoPaymentsCheckout';"
        )
    if exports:
        index_path.write_text("\n".join(exports) + "\n", encoding="utf-8")


def _write_payment_native_scaffolds(out_root: Path, payments: list[str]) -> None:
    native_root = out_root / "native"
    android_root = native_root / "android"
    ios_root = native_root / "ios"
    android_root.mkdir(parents=True, exist_ok=True)
    ios_root.mkdir(parents=True, exist_ok=True)

    package_name = "com.webtonativeoutput.payments"

    if "Iyzico" in payments:
        _write_android_payment_module(android_root, package_name, "IyzicoPayments")
        _write_android_payment_package(android_root, package_name, "IyzicoPayments")
        _write_ios_payment_module(ios_root, "IyzicoPayments")
        _write_ios_payment_bridge(ios_root, "IyzicoPayments")

    if "DodoPayments" in payments:
        _write_android_payment_module(android_root, package_name, "DodoPayments")
        _write_android_payment_package(android_root, package_name, "DodoPayments")
        _write_ios_payment_module(ios_root, "DodoPayments")
        _write_ios_payment_bridge(ios_root, "DodoPayments")

    _write_native_payment_readme(native_root, package_name, payments)


def _write_android_payment_module(root: Path, package_name: str, module_name: str) -> None:
    package_path = package_name.replace(".", "/")
    module_path = root / "app" / "src" / "main" / "java" / package_path
    module_path.mkdir(parents=True, exist_ok=True)
    file_path = module_path / f"{module_name}Module.kt"
    file_path.write_text(
        "package " + package_name + "\n\n"
        "import com.facebook.react.bridge.Promise\n"
        "import com.facebook.react.bridge.ReactApplicationContext\n"
        "import com.facebook.react.bridge.ReactContextBaseJavaModule\n"
        "import com.facebook.react.bridge.ReactMethod\n"
        "import com.facebook.react.module.annotations.ReactModule\n\n"
        f"@ReactModule(name = {module_name}Module.NAME)\n"
        f"class {module_name}Module(reactContext: ReactApplicationContext) : ReactContextBaseJavaModule(reactContext) {{\n"
        "  override fun getName(): String = NAME\n\n"
        "  @ReactMethod\n"
        "  fun startCheckout(checkoutUrl: String, promise: Promise) {\n"
        "    promise.reject(\"NOT_IMPLEMENTED\", \"Native SDK not wired yet\")\n"
        "  }\n\n"
        "  companion object {\n"
        f"    const val NAME = \"{module_name}\"\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )


def _write_android_payment_package(root: Path, package_name: str, module_name: str) -> None:
    package_path = package_name.replace(".", "/")
    module_path = root / "app" / "src" / "main" / "java" / package_path
    module_path.mkdir(parents=True, exist_ok=True)
    file_path = module_path / f"{module_name}Package.kt"
    file_path.write_text(
        "package " + package_name + "\n\n"
        "import com.facebook.react.ReactPackage\n"
        "import com.facebook.react.bridge.NativeModule\n"
        "import com.facebook.react.bridge.ReactApplicationContext\n"
        "import com.facebook.react.uimanager.ViewManager\n\n"
        f"class {module_name}Package : ReactPackage {{\n"
        "  override fun createNativeModules(reactContext: ReactApplicationContext): List<NativeModule> {\n"
        f"    return listOf({module_name}Module(reactContext))\n"
        "  }\n\n"
        "  override fun createViewManagers(reactContext: ReactApplicationContext): List<ViewManager<*, *>> {\n"
        "    return emptyList()\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )


def _write_ios_payment_module(root: Path, module_name: str) -> None:
    file_path = root / f"{module_name}.swift"
    file_path.write_text(
        "import Foundation\n"
        "import React\n\n"
        f"@objc({module_name})\n"
        f"class {module_name}: NSObject {{\n"
        "  @objc\n"
        "  func startCheckout(_ checkoutUrl: String, resolver resolve: RCTPromiseResolveBlock, rejecter reject: RCTPromiseRejectBlock) {\n"
        "    reject(\"NOT_IMPLEMENTED\", \"Native SDK not wired yet\", nil)\n"
        "  }\n\n"
        "  @objc\n"
        "  static func requiresMainQueueSetup() -> Bool {\n"
        "    return false\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )


def _write_ios_payment_bridge(root: Path, module_name: str) -> None:
    file_path = root / f"{module_name}Bridge.m"
    file_path.write_text(
        "#import <React/RCTBridgeModule.h>\n\n"
        f"@interface RCT_EXTERN_MODULE({module_name}, NSObject)\n"
        "RCT_EXTERN_METHOD(startCheckout:(NSString *)checkoutUrl resolver:(RCTPromiseResolveBlock)resolve rejecter:(RCTPromiseRejectBlock)reject)\n"
        "@end\n",
        encoding="utf-8",
    )


def _write_native_payment_readme(root: Path, package_name: str, payments: list[str]) -> None:
    path = root / "README_NATIVE.md"
    lines = [
        "Native payment module scaffolds.",
        "",
        "Steps:",
        "1) Copy native/android and native/ios into your React Native app root.",
        f"2) Update the Android package name in Kotlin files (current: {package_name}).",
        "3) Register the packages in MainApplication (Android).",
        "4) Add the Swift files to your Xcode target (iOS).",
        "5) Wire the native SDKs and implement startCheckout.",
        "",
        "Modules:",
    ]
    for name in payments:
        module_name = f"{name}Payments" if name == "Iyzico" else name
        lines.append(f"- {module_name}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _write_payment_stub(path: Path, name: str) -> None:
    module_name = f"{name}Payments" if name == "Iyzico" else name
    path.write_text(
        "import React, { useEffect } from \"react\";\n"
        "import { ActivityIndicator, NativeModules, Text, View } from \"react-native\";\n\n"
        f"type {name}NativeModule = {{\n"
        "  startCheckout?: (checkoutUrl: string) => Promise<{ status?: string; payload?: unknown }>;\n"
        "};\n\n"
        f"const Native = (NativeModules as Record<string, {name}NativeModule>)[\"{module_name}\"];\n\n"
        f"export type {name}CheckoutProps = {{\n"
        "  checkoutUrl: string;\n"
        "  onComplete?: (status: { status: 'success' | 'cancel' | 'error'; payload?: unknown }) => void;\n"
        "};\n\n"
        f"export default function {name}Checkout(props: {name}CheckoutProps) {{\n"
        "  const { checkoutUrl, onComplete } = props;\n\n"
        "  useEffect(() => {\n"
        "    let active = true;\n"
        "    const run = async () => {\n"
        "      try {\n"
        f"        if (!Native?.startCheckout) throw new Error(\"{name} native SDK not linked\");\n"
        "        const result = await Native.startCheckout(checkoutUrl);\n"
        "        const status =\n"
        "          result?.status === 'cancel' ? 'cancel' : result?.status === 'error' ? 'error' : 'success';\n"
        "        if (active) onComplete?.({ status, payload: result });\n"
        "      } catch (err) {\n"
        "        if (active) onComplete?.({ status: 'error', payload: err });\n"
        "      }\n"
        "    };\n"
        "    run();\n"
        "    return () => {\n"
        "      active = false;\n"
        "    };\n"
        "  }, [checkoutUrl, onComplete]);\n\n"
        "  return (\n"
        "    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 }}>\n"
        "      <ActivityIndicator />\n"
        f"      <Text style={{ marginTop: 8 }}>Opening {name} checkout...</Text>\n"
        "    </View>\n"
        "  );\n"
        "}\n",
        encoding="utf-8",
    )


def _extract_import_modules(text: str) -> set[str]:
    modules: set[str] = set()
    modules.update(re.findall(r'from\s+["\']([^"\']+)["\']', text))
    modules.update(re.findall(r'import\s+["\']([^"\']+)["\']', text))
    modules.update(re.findall(r'require\(\s*["\']([^"\']+)["\']\s*\)', text))
    return modules

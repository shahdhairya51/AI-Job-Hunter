"""
Patch script: fix dashboard layout issues.
Run from the Job AI Agent directory.
"""
import re

with open('dashboard.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Normalize line endings
code = code.replace('\r\n', '\n')

# ── Fix 1: Remove cmd-bar HTML + empty left column, replace with tight 3-col bar ──
old1 = (
    "# ─── TOP COMMAND BAR ──────────────────────────────────────────────────────────\n"
    "st.markdown('<div class=\"cmd-bar\">'\n"
    "            '<div class=\"cmd-bar-logo\">JOB HUNTER AI</div>'\n"
    "            '</div>', unsafe_allow_html=True)\n"
    "\n"
    "# Search + refresh row\n"
    "cmd_left, cmd_search, cmd_right = st.columns([2, 6, 2])\n"
    "with cmd_left:\n"
    "    pass\n"
    "with cmd_search:\n"
    "    search_q = st.text_input(\n"
    "        \"SEARCH\",\n"
    "        placeholder=\"Search by company, title, location, keyword...\",\n"
    "        label_visibility=\"collapsed\",\n"
    "        key=\"global_search\"\n"
    "    )\n"
    "with cmd_right:\n"
    "    if st.button(\"Refresh Data\", use_container_width=True):\n"
    "        st.cache_data.clear()\n"
    "        st.rerun()"
)
new1 = (
    "# ─── TOP BAR ─────────────────────────────────────────────────────────────────\n"
    "tb_logo, tb_search, tb_refresh = st.columns([1.5, 9, 1.5])\n"
    "with tb_logo:\n"
    "    st.markdown(\"<p style='color:#FF6B00;font-family:JetBrains Mono,monospace;"
    "font-weight:800;font-size:0.85rem;margin:0;'>JOB HUNTER AI</p>\", unsafe_allow_html=True)\n"
    "with tb_search:\n"
    "    search_q = st.text_input(\n"
    "        \"SEARCH\", placeholder=\"Search company, title, location, keyword...\",\n"
    "        label_visibility=\"collapsed\", key=\"global_search\"\n"
    "    )\n"
    "with tb_refresh:\n"
    "    if st.button(\"Refresh\", use_container_width=True):\n"
    "        st.cache_data.clear()\n"
    "        st.rerun()"
)
if old1 in code:
    code = code.replace(old1, new1)
    print("Fix 1 applied: top bar")
else:
    print("Fix 1 NOT found — skipping")

# ── Fix 2: Remove Quick Launch div wrappers + label column ──
old2_start = "# ─── QUICK LAUNCH BAR ─────────────────────────────────────────────────────────────\nst.markdown('<div style=\"padding:8px 24px;border-bottom:1px solid #252525;background:#0c0c0c;\">', unsafe_allow_html=True)\nlc0, lc1, lc2, lc3, lc4, lc5, lc6 = st.columns([1.2, 1, 1, 1, 1, 1.8, 1.5])\nwith lc0:\n    st.markdown('<div class=\"launch-label\">Quick Launch</div>', unsafe_allow_html=True)\n"
old2_end  = "st.markdown('</div>', unsafe_allow_html=True)"
old2_body = (
    "with lc1:\n"
    "    if st.button(\"10 min\", use_container_width=True):\n"
    "        launch_discovery(0.17)\n"
    "with lc2:\n"
    "    if st.button(\"1 hour\", use_container_width=True):\n"
    "        launch_discovery(1)\n"
    "with lc3:\n"
    "    if st.button(\"6 hours\", use_container_width=True):\n"
    "        launch_discovery(6)\n"
    "with lc4:\n"
    "    if st.button(\"24 hours\", use_container_width=True):\n"
    "        launch_discovery(24)\n"
    "with lc5:\n"
    "    if st.button(\"Full Discovery (7 days)\", use_container_width=True):\n"
    "        launch_discovery(168)\n"
    "with lc6:\n"
    "    if st.button(\"Run Full Pipeline\", type=\"primary\", use_container_width=True):\n"
    "        launch_discovery(full_pipeline=True)\n"
)
old2 = old2_start + old2_body + old2_end
new2 = (
    "# ─── QUICK LAUNCH ─────────────────────────────────────────────────────────────\n"
    "lc1, lc2, lc3, lc4, lc5, lc6 = st.columns([1, 1, 1, 1, 2, 1.5])\n"
    "with lc1:\n"
    "    if st.button(\"10 min\", use_container_width=True):\n"
    "        launch_discovery(0.17)\n"
    "with lc2:\n"
    "    if st.button(\"1 hour\", use_container_width=True):\n"
    "        launch_discovery(1)\n"
    "with lc3:\n"
    "    if st.button(\"6 hours\", use_container_width=True):\n"
    "        launch_discovery(6)\n"
    "with lc4:\n"
    "    if st.button(\"24 hours\", use_container_width=True):\n"
    "        launch_discovery(24)\n"
    "with lc5:\n"
    "    if st.button(\"Full Discovery (7 days)\", use_container_width=True):\n"
    "        launch_discovery(168)\n"
    "with lc6:\n"
    "    if st.button(\"Run Full Pipeline\", type=\"primary\", use_container_width=True):\n"
    "        launch_discovery(full_pipeline=True)"
)
if old2 in code:
    code = code.replace(old2, new2)
    print("Fix 2 applied: quick launch")
else:
    print("Fix 2 NOT found — trying partial")
    # partial: just remove the div lines and lc0
    code = code.replace(
        "st.markdown('<div style=\"padding:8px 24px;border-bottom:1px solid #252525;background:#0c0c0c;\">', unsafe_allow_html=True)\n",
        ""
    )
    code = code.replace(
        "lc0, lc1, lc2, lc3, lc4, lc5, lc6 = st.columns([1.2, 1, 1, 1, 1, 1.8, 1.5])\n"
        "with lc0:\n"
        "    st.markdown('<div class=\"launch-label\">Quick Launch</div>', unsafe_allow_html=True)\n",
        "lc1, lc2, lc3, lc4, lc5, lc6 = st.columns([1, 1, 1, 1, 2, 1.5])\n"
    )
    code = code.replace("st.markdown('</div>', unsafe_allow_html=True)\n", "")
    print("  partial fix applied")

# ── Fix 3: Replace expander with always-visible filters ──
old3_head = "with st.expander(\"Filters & Sort\", expanded=False):\n"
if old3_head in code:
    # Remove the expander wrapper and de-indent all indented lines inside it
    lines = code.split('\n')
    new_lines = []
    in_expander = False
    expander_started = False
    for i, line in enumerate(lines):
        if 'with st.expander("Filters & Sort"' in line:
            in_expander = True
            expander_started = True
            new_lines.append("# ─── FILTERS (always visible) ───────────────────────────────────────────────────")
            continue
        if in_expander:
            # Lines inside expander have 4-space indent
            if line.startswith('    '):
                new_lines.append(line[4:])  # remove one indent level
            elif line == '':
                new_lines.append(line)
            else:
                # End of expander block
                in_expander = False
                new_lines.append(line)
        else:
            new_lines.append(line)
    code = '\n'.join(new_lines)
    print("Fix 3 applied: expander removed")
else:
    print("Fix 3 NOT found — expander already removed?")

# ── Fix 4: Make column selector full-width (remove the col_opt, col_spacer split) ──
old4 = (
    "    col_opt, col_spacer = st.columns([4, 6])\n"
    "    with col_opt:\n"
    "        visible = st.multiselect("
)
new4 = (
    "    visible = st.multiselect("
)
if old4 in code:
    # Find the end of the multiselect call to also remove the closing 'with' indent
    code = code.replace(
        "    col_opt, col_spacer = st.columns([4, 6])\n"
        "    with col_opt:\n",
        "    "   # just keep the indent, multiselect call follows
    )
    print("Fix 4 applied: full-width column selector")
else:
    print("Fix 4 not needed or already done")

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("DONE — dashboard.py patched and saved")

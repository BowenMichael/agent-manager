# Implementation Plan: Issue #12 - Make Active Sessions Scrollable

## 1. Architectural Overview
The issue stems from default CSS flexbox behaviors within the left sidebar. The `.agents-sidebar` is a column-based flex container sized to `100%` of its parent (`.main-workspace`). Its children include the header, filters, the `.sessions-list`, and the footer.

While `.sessions-list` is set to `flex: 1` to consume available space and `overflow-y: auto` for scrolling, flex items in a column default to `min-height: auto`. This means the element won't shrink smaller than its content's intrinsic height. When populated with multiple session cards, it expands indefinitely, pushing the footer off-screen.

**The Solution:**
1. Override the default minimum height constraint on `.sessions-list` by explicitly setting `min-height: 0`. This allows the element to shrink, respecting the container's bounds and properly triggering the overflow scroll.
2. Prevent sibling elements (header, filters, footer) from inadvertently shrinking under flex container pressure by setting `flex-shrink: 0`.
3. Apply custom webkit scrollbar styles to `.sessions-list` for a polished UI that matches the application's dark theme.

## 2. Target Files & Modular Breakdown
- `agent_manager/static/style.css`
  - **`.sidebar-header`**, **`.sidebar-filters`**, **`.sidebar-footer`**: Update to prevent shrinking (`flex-shrink: 0`).
  - **`.sessions-list`**: Update to allow shrinking (`min-height: 0`).
  - **New Selectors**: Add custom scrollbar styling (`.sessions-list::-webkit-scrollbar`, track, thumb, and hover states).
- *Note: `agent_manager/static/index.html` requires no structural DOM changes as the HTML skeleton is already correct.*

## 3. Step-by-Step Implementation Guide

**Step 1: Constrain the Flex Siblings**
- Locate the `.sidebar-header`, `.sidebar-filters`, and `.sidebar-footer` class definitions in `style.css`.
- Add `flex-shrink: 0;` to each of these blocks. This guarantees these elements will remain pinned at their exact height and never compress when the viewport is small.

**Step 2: Enable Shrinking & Scrolling on the List**
- Locate the `.sessions-list` class definition in `style.css`.
- Ensure `flex: 1;` and `overflow-y: auto;` are present.
- Add `min-height: 0;` to allow the list container to shrink below its content's height, forcing the scrollbar to appear.

**Step 3: Apply Custom Scrollbar Styling**
- Below the `.sessions-list` block in `style.css`, add custom CSS pseudo-elements to style the scrollbar.
- Add `.sessions-list::-webkit-scrollbar` with a small width (e.g., `6px`).
- Add `.sessions-list::-webkit-scrollbar-track` with a transparent background.
- Add `.sessions-list::-webkit-scrollbar-thumb` with a semi-transparent white or gray background (e.g., `rgba(255, 255, 255, 0.1)`) and rounded borders (`border-radius: 4px`).
- Add a hover state for the thumb (`.sessions-list::-webkit-scrollbar-thumb:hover`) to increase opacity slightly for better UX.

## 4. Verification & Testing Criteria

**Expected Behavior:**
- The Active Sessions header, the Active/Archived/All tabs, and the incoming webhook footer must remain permanently visible in the sidebar, regardless of how many session cards are added.
- The `.sessions-list` area between the filters and the footer should independently scroll vertically when containing many cards.
- A custom, themed scrollbar should be visible when scrolling the list.

**Testing Steps (adhering to Command Log Suppression rules):**
1. Start the server in the background, suppressing logs:
   ```powershell
   python main.py > server_run.log 2>&1 &
   ```
2. Open `http://localhost:8000` in a browser.
3. Simulate or insert 10+ agent sessions (via UI trigger or browser devtools by duplicating `.session-card` nodes) to overflow the view.
4. Verify the footer is not pushed off the bottom of the screen.
5. Verify the sessions list scrolls properly and the custom scrollbar appears.
6. Check for failures, kill the server, and clean up logs:
   ```powershell
   # Only inspect if there was an error
   Get-Content -Tail 40 server_run.log
   
   # Cleanup
   Remove-Item server_run.log -ErrorAction SilentlyContinue
   ```

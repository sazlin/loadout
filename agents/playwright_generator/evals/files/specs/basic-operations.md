# TodoMVC — Basic Operations Test Plan

## Application Overview

A todo list with an accessible textbox named "What needs to be done?".

## Test Scenarios

### 1. Adding New Todos
**Seed:** `e2e/seed.spec.ts`

#### 1.1 Add Valid Todo
**Steps:**
1. Click in the "What needs to be done?" input field
2. Type "Buy groceries"
3. Press Enter

**Expected Results:**
- Todo "Buy groceries" appears in the list
- Input is cleared

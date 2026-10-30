# Phase 5 — Unit Management: User Acceptance Testing (UAT) Script

---

### UAT-1: Organize a building into floors
**Steps:**
1. Open a Building property → Floors tab.
2. Add Floor "1" (Ground Floor), Floor "2", Floor "3".

**Expected Result:** All three floors appear, each showing "0 units" until
units are assigned to them.
Pass ⬜ Fail ⬜

---

### UAT-2: Give a unit a number, floor, and asking rent
**Steps:**
1. Create (or open) an Apartment unit inside that building.
2. Set its Unit Number to "2A", assign it to Floor "2" (using the Floor ID
   shown on the Floors tab), and set a Rent Price.

**Expected Result:** The unit's Overview tab shows "Unit 2A", the correct
floor label, and the rent price. Returning to the Floors tab shows Floor
"2" now has 1 unit.
Pass ⬜ Fail ⬜

---

### UAT-3: Track utility meters per unit
**Steps:**
1. On the same unit, set an Electricity Meter Number and a Water Meter
   Number.

**Expected Result:** Both values save and persist after reload — useful
for cross-referencing utility bills against the right unit later.
Pass ⬜ Fail ⬜

---

### UAT-4: Assign a parking spot and storage unit to an apartment
**Steps:**
1. Create a standalone property of type "Parking" and one of type
   "Storage" (same building/owner).
2. On the apartment unit, set its Assigned Parking and Assigned Storage
   to the IDs of those two properties.
3. Try assigning a Villa's ID as the parking space instead.

**Expected Result:** Steps 1-2 succeed, and the unit's Overview shows the
parking/storage property codes. Step 3 is rejected with a clear message —
only actual Parking-type properties can be assigned as parking.
Pass ⬜ Fail ⬜

---

### UAT-5: Try to delete a floor still in use
**Steps:**
1. Attempt to delete Floor "2" from UAT-2, which still has the apartment
   unit assigned to it.

**Expected Result:** The system blocks the deletion with a clear message
— floors with units can't be silently removed, protecting the building's
structure.
Pass ⬜ Fail ⬜

---

### UAT-6: Compare asking price vs. actual signed rent
**Steps:**
1. On a unit with a Rent Price set (e.g. $3,500), create and activate a
   Lease Agreement (Phase 3) for a different, negotiated amount (e.g.
   $3,300).

**Expected Result:** Both figures coexist without conflict — the unit's
"Rent Price" stays the listed/asking figure, while the lease's own rent
amount reflects what was actually agreed. Useful for tracking negotiation
outcomes over time.
Pass ⬜ Fail ⬜

---

## Sign-off

| Scenario | Tester | Date | Result |
|---|---|---|---|
| UAT-1 | | | |
| UAT-2 | | | |
| UAT-3 | | | |
| UAT-4 | | | |
| UAT-5 | | | |
| UAT-6 | | | |

**Overall Phase 5 approval:** ⬜ Approved to proceed to Phase 6  ⬜ Changes requested

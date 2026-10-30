# Phase 4 — Property Management: User Acceptance Testing (UAT) Script

---

### UAT-1: Register a standalone property
**Steps:**
1. Go to Properties → Add Property.
2. Choose "Villa", pick an owner, enter a title and address.
3. Save.

**Expected Result:** The villa appears in the list with an auto-generated
property code (`PRP-000005`), status "Available", and the correct owner
shown.
Pass ⬜ Fail ⬜

---

### UAT-2: Register a building with units inside it
**Steps:**
1. Add Property → "Building", give it a title, save.
2. Add Property again → "Office", same owner, and select the building
   you just created as its "Parent Building".
3. Open the building's detail page → Units tab.

**Expected Result:** The office appears listed as a unit of the building.
Opening the office directly shows it belongs to that parent building.
Pass ⬜ Fail ⬜

---

### UAT-3: Add photos and set a cover image
**Steps:**
1. On any property, go to the Images tab, upload 2-3 photos.
2. Set one as the cover photo.

**Expected Result:** All photos appear in a gallery. Only the chosen photo
shows the "Cover" badge — picking a new cover automatically un-marks the
old one.
Pass ⬜ Fail ⬜

---

### UAT-4: Upload the title deed and track its expiry
**Steps:**
1. On the Documents tab, upload a document as "Title Deed" with an expiry
   date in the past (for testing).

**Expected Result:** The document shows a red "Expired" badge immediately
— useful for spotting properties with lapsed paperwork at a glance.
Pass ⬜ Fail ⬜

---

### UAT-5: Tag amenities
**Steps:**
1. On the Amenities tab, check a few boxes (e.g. Swimming Pool, Parking,
   24/7 Security) and save.
2. Add a brand-new amenity that isn't in the list yet.

**Expected Result:** Selected amenities persist after reload. The new
amenity you typed becomes available to check and to use on other
properties going forward.
Pass ⬜ Fail ⬜

---

### UAT-6: See which lease covers a property
**Steps:**
1. Create a new lease agreement (Phase 3) and select this property from
   the property picker.
2. Activate the lease.
3. Return to the property's Overview tab.

**Expected Result:** The property's "Current Lease Contract" section now
shows the contract number and end date, with a link straight to the
lease record — no manual cross-referencing needed.
Pass ⬜ Fail ⬜

---

### UAT-7: Track a property's full history
**Steps:**
1. On a property you've edited, uploaded images/documents to, and tagged
   amenities on, open the History tab.

**Expected Result:** A complete, plain-English timeline of everything
that's happened to this property record.
Pass ⬜ Fail ⬜

---

### UAT-8: Role boundaries hold for property data
**Steps:**
1. Log in as the seeded Staff user.
2. Open Properties.

**Expected Result:** Staff can browse and view every property (including
images, documents, amenities) but sees no Add/Edit/Delete/Upload controls
anywhere.
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
| UAT-7 | | | |
| UAT-8 | | | |

**Overall Phase 4 approval:** ⬜ Approved to proceed to Phase 5  ⬜ Changes requested

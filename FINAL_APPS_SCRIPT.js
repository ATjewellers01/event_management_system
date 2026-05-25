/**
 * ------------------------------------------------------------------
 * FINAL UPDATED APPS SCRIPT (FULL VERSION)
 * ------------------------------------------------------------------
 * This script handles:
 * 1. GET requests (doGet) - Returns all data for the Leads Dashboard.
 * 2. POST requests (doPost) - Handles 'extract', 'save', and 'read' actions.
 * ------------------------------------------------------------------
 */

/**
 * Handle GET requests to fetch whole sheet data for the Dashboard.
 */
function doGet(e) {
  try {
    // Default sheet for doGet if not specified, assuming "Ai Card" is the dashboard sheet
    const sheetData = getSheetData("Ai Card");
    return ContentService
      .createTextOutput(JSON.stringify({ success: true, data: sheetData }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, message: "Script Error: " + err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Handle POST requests for complex actions.
 */
const SHEET_ID = "1x7eUUxrD_HiChuraWQz-zAkIrMJHAfKyK7OXEfLTYhY";

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      throw new Error("Invalid POST request received.");
    }

    const postData = JSON.parse(e.postData.contents);
    const action = postData.action;
    let result;

    if (action === 'extract') {
      result = extractData(postData.photo1Base64);
    } else if (action === 'save') {
      result = saveData(postData.extractedData, postData.photo1Base64, postData.photo2Base64);
    } else if (action === 'save_event') {
      result = saveEventData(postData.eventData);
    } else if (action === 'save_lead') {
      result = saveLeadData(postData.leadData);
    } else if (action === 'read') {
      result = getSheetData(postData.sheetName);
    } else if (action === 'get_event') {
      result = getEventById(postData.eventId);
    } else if (action === 'get_event_list') {
      result = getEventList();
    } else if (action === 'save_event_card') {
      result = saveEventCardData(postData.extractedData, postData.photo1Base64, postData.photo2Base64, postData.eventInfo);
    } else if (action === 'get_event_data') {
      result = getEventSpecificData(postData.eventId, postData.eventName);
    } else if (action === 'save_visitor_and_get_contact') {
      result = saveVisitorAndGetContact(postData.visitorData);
    } else if (action === 'get_company_profile') {
      result = getCompanyProfile();
    } else if (action === 'save_company_profile') {
      result = saveCompanyProfile(postData.profileData);
    } else {
      throw new Error("Invalid action specified: " + action);
    }

    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, message: "Script Error: " + err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function extractData(photo1Base64) {
  const PYTHON_BACKEND_URL = "https://ocr-reader-botivate.onrender.com";

  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ base64Image: photo1Base64 }),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(PYTHON_BACKEND_URL + "/ocr", options);
  if (response.getResponseCode() !== 200) {
    throw new Error("AI Server Error: " + response.getContentText());
  }
  return JSON.parse(response.getContentText());
}

function saveData(extractedData, photo1Base64, photo2Base64) {
  // --- CONFIGURATION ---
  const FOLDER_ID = "1GGdVdY5OAH-nF1DIJsbcMF6Lgep0d1DS";
  const SHEET_NAME = "Ai Card";
  // ---------------------

  let sheet;
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow([
        "Timestamp", "Card Photo 1", "Card Photo 2", "Company Name", "Industry",
        "Person Name", "Designation", "Phone", "Email", "Website", "Social Media",
        "Address", "Services", "Company Size", "Founded Year", "Registration Status",
        "Trust Score", "People (Founders)", "Is Validated", "Source Link",
        "About Company", "Location"
      ]);
      sheet.getRange(1, 1, 1, 22).setFontWeight("bold").setBackground("#f3f3f3");
    }
  } catch (e) {
    throw new Error("FAILED to access Spreadsheet. Check SHEET_ID. Details: " + e.message);
  }

  let folder;
  try {
    folder = DriveApp.getFolderById(FOLDER_ID);
  } catch (e) {
    throw new Error("FAILED to access Drive Folder. Check FOLDER_ID. Details: " + e.message);
  }

  const timestamp = new Date();

  // Save Image 1
  let url1 = "";
  try {
    const blob1 = Utilities.newBlob(Utilities.base64Decode(photo1Base64), "image/png", "photo1_" + timestamp.getTime() + ".png");
    const file1 = folder.createFile(blob1);
    url1 = file1.getUrl();
  } catch (e) {
    throw new Error("Failed to save Image 1: " + e.message);
  }

  // Save Image 2
  let url2 = "";
  if (photo2Base64 && photo2Base64.trim() !== "") {
    try {
      const blob2 = Utilities.newBlob(Utilities.base64Decode(photo2Base64), "image/png", "photo2_" + timestamp.getTime() + ".png");
      const file2 = folder.createFile(blob2);
      url2 = file2.getUrl();
    } catch (e) {
      url2 = "Error saving image 2: " + e.message;
    }
  }

  // Hyperlink Logic
  let validationLink = extractedData.validation_source || "";
  const companyName = extractedData.company || "Source";

  if (extractedData.is_validated && extractedData.validation_source) {
    const safeUrl = extractedData.validation_source.replace(/"/g, '""');
    const safeName = companyName.replace(/"/g, '""');
    validationLink = `=HYPERLINK("${safeUrl}", "${safeName} Link")`;
  }

  // Format Key People (Founder/CEO + Contact)
  let keyPeopleString = "";
  if (extractedData.key_people && Array.isArray(extractedData.key_people)) {
    keyPeopleString = extractedData.key_people.map(p => {
      let details = p.name + " (" + p.role + ")";
      if (p.contact && p.contact !== "Not Found") {
        details += " - " + p.contact;
      }
      return details;
    }).join("\n");
  } else {
    let parts = [];
    if (extractedData.founder) parts.push("Founder: " + extractedData.founder);
    if (extractedData.ceo) parts.push("CEO: " + extractedData.ceo);
    if (extractedData.owner) parts.push("Owner: " + extractedData.owner);
    keyPeopleString = parts.join("\n");
  }

  // Append Row (Columns A-V)
  sheet.appendRow([
    timestamp,                          // A
    url1,                               // B
    url2,                               // C
    extractedData.company || "",        // D
    extractedData.industry || "",       // E 
    extractedData.name || "",           // F
    extractedData.title || "",          // G 
    extractedData.phone || "",          // H
    extractedData.email || "",          // I
    extractedData.website || "",        // J 
    extractedData.social_media || "",   // K 
    extractedData.address || "",        // L
    extractedData.services || "",       // M 
    extractedData.company_size || "",   // N 
    extractedData.established_year || extractedData.founded_year || "", // O 
    extractedData.registration_status || "", // P 
    extractedData.trust_score || "",    // Q
    keyPeopleString,                    // R 
    extractedData.is_validated,         // S
    validationLink,                     // T
    extractedData.about_the_company || "", // U
    extractedData.location || ""          // V
  ]);

  return { message: "✅ Data saved successfully!" };
}

function saveEventData(eventData) {
  const SHEET_NAME = "Event Details";

  // --- Open Sheet (auto-create if missing) ---
  let sheet;
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) sheet = ss.insertSheet(SHEET_NAME);
  } catch (e) {
    throw new Error("FAILED to access Spreadsheet: " + e.message);
  }

  // --- Auto-create header row if sheet is empty ---
  if (sheet.getLastRow() === 0) {
    const headers = [
      "Timestamp",      // A
      "Event ID",       // B
      "Event Name",     // C
      "Start Date",     // D
      "End Date",       // E
      "Location",       // F
      "Description",    // G
      "Member Name",    // H
      "Designation",    // I
      "Phone"           // J
    ];
    sheet.appendRow(headers);
    sheet.getRange(1, 1, 1, headers.length)
      .setFontWeight("bold")
      .setBackground("#d9e8fb")
      .setFontColor("#1a3a6b");
    sheet.setFrozenRows(1);
  }

  const timestamp = new Date();

  // --- Generate sequential Event ID ---
  let eventId = "EVT-001";
  try {
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      const bCol = sheet.getRange(2, 2, lastRow - 1, 1).getValues();
      let lastIdValue = "";
      for (let i = bCol.length - 1; i >= 0; i--) {
        if (bCol[i][0] && typeof bCol[i][0] === 'string' && bCol[i][0].startsWith("EVT-")) {
          lastIdValue = bCol[i][0];
          break;
        }
      }
      if (lastIdValue) {
        const lastNum = parseInt(lastIdValue.replace("EVT-", "").trim(), 10);
        if (!isNaN(lastNum)) {
          eventId = "EVT-" + (lastNum + 1).toString().padStart(3, "0");
        }
      }
    }
  } catch (e) {
    eventId = "EVT-" + Math.floor(1000 + Math.random() * 9000);
  }

  const members = eventData.teamMembers || [];

  if (members.length === 0) {
    // No members — save one row with event details only
    sheet.appendRow([
      timestamp,
      eventId,
      eventData.eventName   || "",
      eventData.startDate   || "",
      eventData.endDate     || "",
      eventData.location    || "",
      eventData.description || "",
      "", "", ""  // Member cols empty
    ]);
  } else {
    members.forEach((m, index) => {
      if (index === 0) {
        // First row: Full event details + Member 1
        sheet.appendRow([
          timestamp,
          eventId,
          eventData.eventName   || "",
          eventData.startDate   || "",
          eventData.endDate     || "",
          eventData.location    || "",
          eventData.description || "",
          m.name        || "",
          m.designation || "",
          m.phone       || ""
        ]);
      } else {
        // Subsequent rows: Event ID only (to link back) + member info
        sheet.appendRow([
          "",       // A: Timestamp blank
          eventId,  // B: Event ID (for reference)
          "", "", "", "", "",          // C–G: blank
          m.name        || "",         // H
          m.designation || "",         // I
          m.phone       || ""          // J
        ]);
      }
    });
  }

  return {
    success: true,
    message: "✅ Event '" + eventData.eventName + "' saved. ID: " + eventId,
    eventId: eventId
  };
}


function getEventList() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheetByName("Event Details");
  if (!sheet) return { success: true, data: [] };
  
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return { success: true, data: [] };
  
  const events = [];
  for (let i = 1; i < data.length; i++) {
    // Column B is Event ID, Column C is Event Name, D: Start, E: End
    if (data[i][1] && data[i][2]) {
      events.push({
        id: data[i][1],
        name: data[i][2],
        startDate: data[i][3],
        endDate: data[i][4],
        location: data[i][5] || ""
      });
    }
  }
  return { success: true, data: events };
}

function saveEventCardData(extractedData, photo1Base64, photo2Base64, eventInfo) {
  const SHEET_NAME = "Event Ai Card";
  const FOLDER_ID = "1GGdVdY5OAH-nF1DIJsbcMF6Lgep0d1DS";
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);
  
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow([
      "Timestamp", "Event ID", "Event Name", "Event Start Date", "Event End Date",
      "Card Photo 1", "Card Photo 2", "Company Name", "Industry", "Person Name",
      "Designation", "Phone", "Email", "Website", "Social Media", "Address",
      "Services", "Company Size", "Founded Year", "Registration Status",
      "Trust Score", "People (Founders)", "Is Validated", "Source Link",
      "About Company", "Location"
    ]);
    sheet.getRange(1, 1, 1, 26).setFontWeight("bold").setBackground("#f3f3f3");
  }

  let folder;
  try { folder = DriveApp.getFolderById(FOLDER_ID); } catch (e) { throw new Error("Drive Folder Error: " + e.message); }

  const timestamp = new Date();
  
  const saveImage = (base64, prefix) => {
    if (!base64 || base64.trim() === "") return "";
    try {
      const blob = Utilities.newBlob(Utilities.base64Decode(base64), "image/jpeg", prefix + "_" + timestamp.getTime() + ".jpg");
      const file = folder.createFile(blob);
      return file.getUrl();
    } catch (e) { return "Error: " + e.message; }
  };

  const img1 = saveImage(photo1Base64, "front");
  const img2 = saveImage(photo2Base64, "back");
  
  const d = extractedData || {};
  
  sheet.appendRow([
    timestamp,
    eventInfo.id || "N/A",
    eventInfo.name || "N/A",
    eventInfo.startDate || "N/A",
    eventInfo.endDate || "N/A",
    img1, img2,
    d.company_name || d.company || "",
    d.industry || "",
    d.person_name || d.name || "",
    d.designation || d.title || "",
    d.phone || "",
    d.email || "",
    d.website || "",
    d.social_media || "",
    d.address || "",
    d.services || "",
    d.company_size || "",
    d.founded_year || d.established_year || "",
    d.registration_status || "",
    d.trust_score || "",
    d.people || d.key_people || "",
    d.is_validated || "",
    d.source_link || d.validation_source || "",
    d.about_company || d.about_the_company || "",
    d.location || ""
  ]);

  return { success: true, message: "Card saved to Event Hub!" };
}

function getEventById(eventId) {
    if (!eventId) return { success: false, message: "No Event ID provided" };

    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName("Event Details");
    if (!sheet) return { success: false, message: "Event not found" };
    
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    
    // Find the row where Column B matches eventId
    for (let i = 1; i < data.length; i++) {
        // Log for debugging (visible in Apps Script logs)
        // console.log("Checking row " + i + ": " + data[i][1]);
        if (String(data[i][1]).trim() == String(eventId).trim()) {
            const result = {};
            headers.forEach((h, idx) => {
                result[h] = data[i][idx];
            });
            return { success: true, data: result };
        }
    }
    
    return { success: false, message: "Event not found" };
}

/**
 * Fetch specific data for an event (Cards + Visitors)
 */
function getEventSpecificData(eventId, eventName) {
    if (!eventId && !eventName) return { success: false, message: "No Event identifier provided" };
    const ss = SpreadsheetApp.openById(SHEET_ID);
    
    const cardSheet = ss.getSheetByName("Event Ai Card");
    const visitorSheet = ss.getSheetByName("Visitor Details");
    
    const idStr = eventId ? String(eventId).trim().toLowerCase() : null;
    const nameStr = eventName ? String(eventName).trim().toLowerCase() : null;

    let cards = [];
    if (cardSheet) {
        const data = cardSheet.getDataRange().getValues();
        const headers = data[0];
        // Event ID: Col B (1), Event Name: Col C (2)
        for (let i = 1; i < data.length; i++) {
            const rowId = String(data[i][1]).trim().toLowerCase();
            const rowName = String(data[i][2]).trim().toLowerCase();
            
            if ((idStr && rowId === idStr) || (nameStr && rowName === nameStr)) {
                const obj = {};
                headers.forEach((h, idx) => obj[h] = data[i][idx]);
                cards.push(obj);
            }
        }
    }
    
    let visitors = [];
    if (visitorSheet) {
        const data = visitorSheet.getDataRange().getValues();
        const headers = data[0];
        // Event ID: Col B (1), Event Name: Col C (2)
        for (let i = 1; i < data.length; i++) {
            const rowId = String(data[i][1]).trim().toLowerCase();
            const rowName = String(data[i][2]).trim().toLowerCase();

            if ((idStr && rowId === idStr) || (nameStr && rowName === nameStr)) {
                const obj = {};
                headers.forEach((h, idx) => obj[h] = data[i][idx]);
                visitors.push(obj);
            }
        }
    }
    
    return { success: true, cards: cards, visitors: visitors };
}

/**
 * Save Lead Data from the QR Scan Form
 */
function saveLeadData(leadData) {
  const SHEET_NAME = "Visitor Details";
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);
  
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow([
      "Timestamp", 
      "Event ID",
      "Event Name",
      "Visitor Name", 
      "Visitor Mobile", 
      "Visitor Email", 
      "Visitor Organization", 
      "Visitor Designation", 
      "Message"
    ]);
    sheet.getRange(1, 1, 1, 9).setFontWeight("bold").setBackground("#f3f3f3");
  }
  
  const timestamp = new Date();
  sheet.appendRow([
    timestamp,
    leadData.eventId || "N/A",
    leadData.eventName || "N/A",
    leadData.fullName,
    leadData.mobile,
    leadData.email,
    leadData.organization,
    leadData.designation,
    leadData.message
  ]);
  
  return { success: true, message: "Lead saved successfully!" };
}

/**
 * Save new Visitor from QR code form and return Event Contact Info for vCard 
 */
function saveVisitorAndGetContact(visitorData) {
  const SHEET_NAME = "Visitor Details";
  const ss = SpreadsheetApp.openById(SHEET_ID);
  
  // 1. Fetch the Event Organizer contact info first to get Event Name
  const eventSheet = ss.getSheetByName("Event Details");
  let contactInfo = null;
  let eventName = "N/A";
  
  if (eventSheet) {
    const data = eventSheet.getDataRange().getValues();
    const headers = data[0];
    
    // Find the row where Column B matches eventId
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][1]).trim().toLowerCase() === String(visitorData.eventId).trim().toLowerCase()) {
        const rowData = {};
        headers.forEach((h, idx) => {
          rowData[h] = data[i][idx];
        });
        
        eventName = rowData["Event Name"] || "N/A";
        let managerName = rowData["Member Name"] || rowData["Key Person Name"] || rowData["Event Name"];
        
        contactInfo = {
          name: managerName,
          company: rowData["Company Name"] || rowData["Event Name"],
          tagline: rowData["Tagline"] || "",
          industry: rowData["Industry"] || "",
          foundedYear: rowData["Founded Year"] || "",
          phone: rowData["Phone"] || rowData["Official Phone"] || "N/A",
          altPhone: rowData["Alternate Phone"] || "",
          email: rowData["Official Email"] || "N/A",
          whatsapp: rowData["WhatsApp Number"] || "",
          address: rowData["Address Line 1"] || rowData["Location"] || "",
          city: rowData["City"] || "",
          state: rowData["State"] || "",
          pincode: rowData["Pincode"] || "",
          country: rowData["Country"] || "",
          website: rowData["Website URL"] || "",
          mapsLink: rowData["Google Maps Link"] || "",
          linkedin: rowData["LinkedIn profile link"] || "",
          instagram: rowData["Instagram profile link"] || "",
          facebook: rowData["Facebook profile link"] || "",
          twitter: rowData["Twitter profile link"] || "",
          services: rowData["Services Provided"] || "",
          about: rowData["About the company"] || ""
        };
        break;
      }
    }
  }

  if (!contactInfo) {
    // If not found, return empty placeholder
    contactInfo = {
       name: "Event Organizer",
       company: visitorData.eventId,
       phone: "",
       email: "",
       website: ""
    };
  }

  // 2. Save the visitor details
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow([
      "Timestamp", 
      "Event ID",
      "Event Name",
      "Visitor Name", 
      "Visitor Mobile", 
      "Visitor Email", 
      "Visitor Organization", 
      "Visitor Designation", 
      "Message"
    ]);
    sheet.getRange(1, 1, 1, 9).setFontWeight("bold").setBackground("#f3f3f3");
  }
  
  const timestamp = new Date();
  sheet.appendRow([
    timestamp,
    visitorData.eventId || "N/A",
    eventName,
    visitorData.visitorName || "",
    visitorData.visitorMobile || "",
    visitorData.visitorEmail || "",
    visitorData.visitorOrg || "",
    visitorData.visitorDesig || "",
    visitorData.message || ""
  ]);

  // 3. Merging with Global Company Profile
  const globalProfile = getCompanyProfile().profile;
  if (globalProfile && globalProfile.companyName) {
    contactInfo = {
      name: globalProfile.keyPersonName || contactInfo.name,
      company: globalProfile.companyName,
      tagline: globalProfile.tagline || "",
      industry: globalProfile.industry || "",
      foundedYear: globalProfile.foundedYear || "",
      // Use Key Person's Direct Info if available, otherwise fallback to Official
      phone: globalProfile.keyPersonPhone || globalProfile.officialPhone || "N/A",
      altPhone: globalProfile.alternatePhone || "",
      email: globalProfile.keyPersonEmail || globalProfile.officialEmail || "N/A",
      whatsapp: globalProfile.whatsappNumber || "",
      address: globalProfile.addressLine || "",
      city: globalProfile.city || "",
      state: globalProfile.state || "",
      pincode: globalProfile.pincode || "",
      country: globalProfile.country || "",
      website: globalProfile.websiteUrl || "",
      linkedin: globalProfile.linkedin || "",
      twitter: globalProfile.twitter || "",
      facebook: globalProfile.facebook || "",
      instagram: globalProfile.instagram || "",
      services: globalProfile.services || "",
      about: globalProfile.aboutCompany || "",
      mapsLink: globalProfile.googleMapsLink || "",
      logoBase64: globalProfile.logoBase64 || ""
    };
  }

  return { success: true, message: "Visitor saved successfully", contactInfo: contactInfo };
}

/**
 * Helper function to fetch all data from the sheet for Dashboard viewing.
 */
function getSheetData(SHEET_NAME) {
  if (!SHEET_NAME) SHEET_NAME = "Ai Card";

  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) return { success: true, data: [] };

  const range = sheet.getDataRange();
  const values = range.getValues();
  const formulas = range.getFormulas();

  if (values.length < 2) return { success: true, data: [] };
  
  const headers = values[0];
  const data = [];
  
  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const rowFormulas = formulas[i];
    const obj = {};
    headers.forEach((header, index) => {
      // Use formula if it exists (for hyperlinks), otherwise use value
      obj[header] = rowFormulas[index] || row[index];
    });
    data.push(obj);
  }
  
  return { success: true, data: data };
}

/**
 * Fetch Company Profile from 'Company Profile' Sheet
 */
function getCompanyProfile() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheetByName("Company Profile");
  
  if (!sheet || sheet.getLastRow() < 2) {
    return { success: true, profile: {} };
  }
  
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const lastRow = sheet.getRange(sheet.getLastRow(), 1, 1, sheet.getLastColumn()).getValues()[0];
  
  const profile = {};
  headers.forEach((h, i) => {
    // Map sheet headers to frontend profile keys
    const hTrim = h ? h.trim() : "";
    if (!hTrim || hTrim === "Timestamp") return;
    
    // Reverse mapping
    if (hTrim === "Company Name") profile.companyName = lastRow[i];
    if (hTrim === "Tagline") profile.tagline = lastRow[i];
    if (hTrim === "Industry") profile.industry = lastRow[i];
    if (hTrim === "Founded Year") profile.foundedYear = lastRow[i];
    if (hTrim === "Official Phone") profile.officialPhone = lastRow[i];
    if (hTrim === "Alternate Phone") profile.alternatePhone = lastRow[i];
    if (hTrim === "Official Email") profile.officialEmail = lastRow[i];
    if (hTrim === "WhatsApp Number") profile.whatsappNumber = lastRow[i];
    if (hTrim === "Address Line 1") profile.addressLine = lastRow[i];
    if (hTrim === "City") profile.city = lastRow[i];
    if (hTrim === "State") profile.state = lastRow[i];
    if (hTrim === "Pincode") profile.pincode = lastRow[i];
    if (hTrim === "Country") profile.country = lastRow[i];
    if (hTrim === "Website URL") profile.websiteUrl = lastRow[i];
    if (hTrim === "Google Maps Link") profile.googleMapsLink = lastRow[i];
    if (hTrim === "LinkedIn") profile.linkedin = lastRow[i];
    if (hTrim === "Instagram") profile.instagram = lastRow[i];
    if (hTrim === "Facebook") profile.facebook = lastRow[i];
    if (hTrim === "Twitter") profile.twitter = lastRow[i];
    if (hTrim === "Services Provided") profile.services = lastRow[i];
    if (hTrim === "About the company") profile.aboutCompany = lastRow[i];
    if (hTrim === "Key Person Name") profile.keyPersonName = lastRow[i];
    if (hTrim === "Key Person Designation") profile.keyPersonDesignation = lastRow[i];
    if (hTrim === "Key Person Phone") profile.keyPersonPhone = lastRow[i];
    if (hTrim === "Key Person Email") profile.keyPersonEmail = lastRow[i];
    if (hTrim === "Logo") profile.logoBase64 = lastRow[i];
  });

  return { success: true, profile: profile };
}

/**
 * Save Company Profile to 'Company Profile' Sheet
 */
function saveCompanyProfile(profileData) {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName("Company Profile");

  if (!sheet) {
    sheet = ss.insertSheet("Company Profile");
    sheet.appendRow([
      "Timestamp", "Company Name", "Tagline", "Industry", "Founded Year",
      "Official Phone", "Alternate Phone", "Official Email", "WhatsApp Number",
      "Address Line 1", "City", "State", "Pincode", "Country",
      "Website URL", "Google Maps Link", "LinkedIn", "Instagram", "Facebook", "Twitter",
      "Services Provided", "About the company",
      "Key Person Name", "Key Person Designation", "Key Person Phone", "Key Person Email",
      "Logo"
    ]);
    sheet.getRange(1, 1, 1, 27).setFontWeight("bold").setBackground("#f3f3f3");
  }

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const newRow = new Array(headers.length).fill("");
  newRow[0] = new Date(); // Timestamp
  
  headers.forEach((h, i) => {
    const hTrim = h ? h.trim() : "";
    if (!hTrim || hTrim === "Timestamp") return;
    
    if (hTrim === "Company Name") newRow[i] = profileData.companyName || "";
    if (hTrim === "Tagline") newRow[i] = profileData.tagline || "";
    if (hTrim === "Industry") newRow[i] = profileData.industry || "";
    if (hTrim === "Founded Year") newRow[i] = profileData.foundedYear || "";
    if (hTrim === "Official Phone") newRow[i] = profileData.officialPhone || "";
    if (hTrim === "Alternate Phone") newRow[i] = profileData.alternatePhone || "";
    if (hTrim === "Official Email") newRow[i] = profileData.officialEmail || "";
    if (hTrim === "WhatsApp Number") newRow[i] = profileData.whatsappNumber || "";
    if (hTrim === "Address Line 1") newRow[i] = profileData.addressLine || "";
    if (hTrim === "City") newRow[i] = profileData.city || "";
    if (hTrim === "State") newRow[i] = profileData.state || "";
    if (hTrim === "Pincode") newRow[i] = profileData.pincode || "";
    if (hTrim === "Country") newRow[i] = profileData.country || "";
    if (hTrim === "Website URL") newRow[i] = profileData.websiteUrl || "";
    if (hTrim === "Google Maps Link") newRow[i] = profileData.googleMapsLink || "";
    if (hTrim === "LinkedIn") newRow[i] = profileData.linkedin || "";
    if (hTrim === "Instagram") newRow[i] = profileData.instagram || "";
    if (hTrim === "Facebook") newRow[i] = profileData.facebook || "";
    if (hTrim === "Twitter") newRow[i] = profileData.twitter || "";
    if (hTrim === "Services Provided") newRow[i] = profileData.services || "";
    if (hTrim === "About the company") newRow[i] = profileData.aboutCompany || "";
    if (hTrim === "Key Person Name") newRow[i] = profileData.keyPersonName || "";
    if (hTrim === "Key Person Designation") newRow[i] = profileData.keyPersonDesignation || "";
    if (hTrim === "Key Person Phone") newRow[i] = profileData.keyPersonPhone || "";
    if (hTrim === "Key Person Email") newRow[i] = profileData.keyPersonEmail || "";
    if (hTrim === "Logo") newRow[i] = profileData.logoBase64 || "";
  });

  if (sheet.getLastRow() < 2) {
    sheet.appendRow(newRow);
  } else {
    // Overwrite row 2 to always keep latest 
    sheet.getRange(2, 1, 1, newRow.length).setValues([newRow]);
  }
  
  return { success: true, message: "Company profile explicitly saved in the Sheet." };
}

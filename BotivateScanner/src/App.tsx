import { QRCodeSVG } from "qrcode.react"
import { useState, useEffect } from "react"
import { 
  Phone, Mail, MapPin, Globe, Download, QrCode, Smartphone, Share2, 
  Linkedin, Instagram, Facebook, Twitter, ExternalLink, User
} from "lucide-react"
import jsPDF from "jspdf"
// @ts-ignore - QRCode library doesn't have TypeScript definitions
import QRCodeLib from "qrcode"

interface ContactInfo {
  firstName: string
  lastName: string
  title: string
  organization: string
  phone: string
  email: string
  address: string
  city: string
  state: string
  pincode: string
  country: string
  website: string
  logo: string
  tagline?: string
  industry?: string
  whatsapp?: string
  linkedin?: string
  instagram?: string
  facebook?: string
  twitter?: string
  services?: string
  about?: string
  mapsLink?: string
}

interface LeadFormData {
  fullName: string;
  mobile: string;
  email: string;
  organization: string;
  designation: string;
  message: string;
}

function LeadForm({ onSubmit, cardOwner }: { onSubmit: (data: LeadFormData) => void, cardOwner: string }) {
  const [formData, setFormData] = useState<LeadFormData>({
    fullName: "",
    mobile: "",
    email: "",
    organization: "",
    designation: "",
    message: ""
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    await onSubmit(formData);
    setSubmitting(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4 font-sans">
      <div className="max-w-md w-full bg-white rounded-[2.5rem] shadow-2xl p-8 border border-white/50 relative overflow-hidden">
        {/* Abstract Background Element */}
        <div className="absolute -top-24 -right-24 w-64 h-64 bg-blue-100/50 rounded-full blur-3xl -z-10"></div>
        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-indigo-100/50 rounded-full blur-3xl -z-10"></div>

        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center p-3 bg-blue-600 text-white rounded-2xl shadow-lg mb-4">
            <User className="w-6 h-6" />
          </div>
          <h2 className="text-3xl font-black text-slate-800 tracking-tight">Connect with</h2>
          <p className="text-blue-600 font-bold uppercase tracking-widest text-xs mt-1">{cardOwner}</p>
          <p className="text-slate-400 text-sm mt-4 px-4 font-medium">Please fill in your details to view the full profile and save contact information.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Pura Naam (Full Name)</label>
            <input
              required
              type="text"
              placeholder="Ex: Rajesh Kumar"
              className="w-full px-5 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none text-slate-700 font-semibold"
              value={formData.fullName}
              onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-1 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Mobile / WhatsApp</label>
              <input
                required
                type="tel"
                placeholder="+91 00000 00000"
                className="w-full px-5 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none text-slate-700 font-semibold"
                value={formData.mobile}
                onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Email Address</label>
              <input
                required
                type="email"
                placeholder="rajesh@company.com"
                className="w-full px-5 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none text-slate-700 font-semibold"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Company ka Naam (Organization)</label>
            <input
              required
              type="text"
              placeholder="Ex: ABC Pvt Ltd"
              className="w-full px-5 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none text-slate-700 font-semibold"
              value={formData.organization}
              onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Job Title (Designation)</label>
            <input
              required
              type="text"
              placeholder="Ex: Marketing Manager"
              className="w-full px-5 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none text-slate-700 font-semibold"
              value={formData.designation}
              onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Chhota Message (Optional)</label>
            <textarea
              placeholder="Reason for contact..."
              className="w-full px-5 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none text-slate-700 font-semibold min-h-[100px] resize-none"
              value={formData.message}
              onChange={(e) => setFormData({ ...formData, message: e.target.value })}
            />
          </div>

          <button
            disabled={submitting}
            type="submit"
            className="w-full bg-slate-900 text-white font-black py-4 rounded-2xl shadow-xl flex items-center justify-center gap-3 transition-all active:scale-95 hover:bg-black mt-4 disabled:opacity-70"
          >
            {submitting ? "Submitting..." : "SUBMIT & VIEW PROFILE"}
          </button>
        </form>
      </div>
    </div>
  );
}

function App() {
  const [screenSize, setScreenSize] = useState({ width: 1024 })
  const [contactInfo, setContactInfo] = useState<ContactInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(true)
  const [eventId, setEventId] = useState<string | null>(null)
  const [eventName, setEventName] = useState<string>("")

  useEffect(() => {
    setScreenSize({ width: window.innerWidth })
    const handleResize = () => setScreenSize({ width: window.innerWidth })
    window.addEventListener('resize', handleResize)

    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    setEventId(id);

    // Check if lead already submitted in this session
    const hasSubmitted = sessionStorage.getItem(`lead_submitted_${id || 'default'}`);
    if (hasSubmitted) {
      setShowForm(false);
    }

    if (id) {
      fetchEventData(id);
    } else {
      // No event id in the URL — render an empty card. Real data populates
      // when the user navigates from a scanned QR with a valid event id.
      setContactInfo({
        firstName: "",
        lastName: "",
        title: "",
        organization: "",
        phone: "",
        email: "",
        address: "",
        city: "",
        state: "",
        pincode: "",
        country: "",
        website: "",
        logo: "",
        industry: "",
        tagline: ""
      });
      setLoading(false);
    }
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const convertDriveLink = (url: string) => {
    if (!url) return url;
    let cleanUrl = String(url).trim();
    if (cleanUrl.startsWith('=HYPERLINK')) {
      const match = cleanUrl.match(/"(.*?)"/);
      if (match) cleanUrl = match[1];
    }
    if (cleanUrl.includes('drive.google.com')) {
      const match = cleanUrl.match(/\/d\/(.+?)(\/|\?|$)/) || cleanUrl.match(/id=(.+?)(&|$)/);
      if (match && match[1]) return `https://drive.google.com/uc?id=${match[1]}`;
    }
    return cleanUrl;
  };

  const wrapWithProxy = (url: string) => {
    if (!url || url.includes('localhost') || url.startsWith('images/') || !url.startsWith('http')) return url;
    return `/proxy-image?url=${encodeURIComponent(url)}`;
  };

  const fetchEventData = async (id: string) => {
    try {
      // Goes through our own backend (Turso), not Apps Script. Same response
      // shape, so the field mapping below is unchanged.
      const response = await fetch(`/get-event/${encodeURIComponent(id)}`);
      const res = await response.json();
      if (res.success && res.data) {
        const d = res.data;
        const allKeys = Object.keys(d);
        const logoKey = allKeys.find(k => k.toLowerCase().includes('logo') || k.toLowerCase().includes('photo') || k.toLowerCase().includes('image'));
        const rawLogo = logoKey ? d[logoKey] : "";
        const processedLogo = convertDriveLink(rawLogo);
        const finalLogo = wrapWithProxy(processedLogo);
        const eName = d["Event Name"] || "Unknown Event";
        setEventName(eName);

        setContactInfo({
          firstName: d["Member Name"] ? d["Member Name"].split(' ')[0] : (d["Event Name"] || "Event"),
          lastName: d["Member Name"] ? d["Member Name"].split(' ').slice(1).join(' ') : "",
          title: d["Designation"] || "Event Organizer",
          organization: d["Company Name"] || "",
          phone: d["Member Phone"] || d["Official Phone"] || d["Mobile Number"] || "",
          email: d["Official Email"] || "",
          address: d["Address Line"] || "",
          city: d["City"] || "",
          state: d["State"] || "",
          pincode: d["Pincode"] || "",
          country: d["Country"] || "",
          website: d["Website URL"] || d["Website"] || "",
          logo: finalLogo || "",
          tagline: d["Tagline"] || "",
          industry: d["Industry"] || "",
          whatsapp: d["WhatsApp Number"] || "",
          linkedin: d["LinkedIn"] || "",
          instagram: d["Instagram"] || "",
          facebook: d["Facebook"] || "",
          twitter: d["Twitter/X"] || d["Twitter"] || "",
          services: d["Services Offered"] || "",
          about: d["About Company"] || "",
          mapsLink: d["Google Maps Link"] || ""
        });
      }
    } catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const handleLeadSubmit = async (data: LeadFormData) => {
    try {
      const leadData = {
        ...data,
        eventId: eventId,
        eventName: eventName,
        ownerName: contactInfo ? `${contactInfo.firstName} ${contactInfo.lastName}` : "Unknown",
        ownerOrg: contactInfo?.organization || "N/A"
      };

      await fetch("/submit-lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadData })
      });
      
      sessionStorage.setItem(`lead_submitted_${eventId || 'default'}`, "true");
      setShowForm(false);
    } catch (e) {
      console.error(e);
      // Even if it fails, let them see the profile (optional choice, but better for UX)
      setShowForm(false);
    }
  };

  const generateVCard = (contact: ContactInfo): string => {
    return `BEGIN:VCARD
VERSION:3.0
N:${contact.lastName};${contact.firstName};;;
FN:${contact.firstName} ${contact.lastName}
TITLE:${contact.title}
ORG:${contact.organization}
TEL;TYPE=CELL,VOICE:+91${contact.phone}
EMAIL;TYPE=PREF,INTERNET:${contact.email}
ADR;TYPE=WORK:;;${contact.address};${contact.city};${contact.state};${contact.pincode};${contact.country}
URL:${contact.website}
END:VCARD`.trim()
  }

  const downloadVCard = () => {
    if (!contactInfo) return;
    const name = `${contactInfo.firstName} ${contactInfo.lastName}`;
    const url = `/vcard-direct?name=${encodeURIComponent(name)}&org=${encodeURIComponent(contactInfo.organization)}&phone=${encodeURIComponent(contactInfo.phone)}&email=${encodeURIComponent(contactInfo.email)}`;
    window.location.href = url;
  }

  const generateQRCodeDataURL = async (text: string, options = {}): Promise<string> => {
    return await QRCodeLib.toDataURL(text, { errorCorrectionLevel: "H", type: "image/png", margin: 1, width: 1000, ...options })
  }

  const loadImageAsDataURL = (url: string): Promise<string> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = img.naturalWidth; canvas.height = img.naturalHeight
        const ctx = canvas.getContext('2d'); if (!ctx) return reject('No ctx');
        ctx.drawImage(img, 0, 0); resolve(canvas.toDataURL('image/png'))
      }
      img.onerror = () => reject('Load fail'); img.src = url;
    })
  }

  const downloadContactPDF = async () => {
    if (!contactInfo) return;
    try {
      // New: Make PDF dimension fit the card exactly (Full Size)
      const cw = 200; const ch = 110
      const pdf = new jsPDF("l", "mm", [cw + 20, ch + 20])
      const pw = cw + 20; const ph = ch + 20
      const cx = 10; const cy = 10

      // 1. ALL-AROUND 3D Shadow (Glow Effect)
      pdf.setDrawColor(210, 210, 210); pdf.setLineWidth(0.3)
      for(let i=1; i<=6; i++) {
          // Centered shadow layers
          pdf.roundedRect(cx - i/3, cy - i/3, cw + (i*2/3), ch + (i*2/3), 6, 6, "S")
      }

      // 2. Card Base (Pristine White)
      pdf.setDrawColor(240, 240, 240); pdf.setFillColor(255, 255, 255); pdf.setLineWidth(0.1)
      pdf.roundedRect(cx, cy, cw, ch, 6, 6, "FD")

      const splitX = cx + cw * 0.46
      // PREMIUM S-CURVE (Image 2 Match)
      pdf.setFillColor(15, 23, 42)
      // @ts-ignore
      pdf.moveTo(splitX, cy)
      // @ts-ignore
      pdf.curveTo(splitX - 18, cy + 20, splitX + 10, cy + ch - 20, splitX - 18, cy + ch)
      // @ts-ignore
      pdf.lineTo(cx + cw - 6, cy + ch); pdf.curveTo(cx + cw, cy + ch, cx + cw, cy + ch, cx + cw, cy + ch - 6)
      // @ts-ignore
      pdf.lineTo(cx + cw, cy + 6); pdf.curveTo(cx + cw, cy, cx + cw, cy, cx + cw - 6, cy)
      pdf.fill()

      // SHARP ORANGE ACCENT CURVE
      pdf.setDrawColor(245, 158, 11); pdf.setLineWidth(2.2)
      // @ts-ignore
      pdf.moveTo(splitX - 2, cy)
      // @ts-ignore
      pdf.curveTo(splitX - 20, cy + 20, splitX + 8, cy + ch - 20, splitX - 20, cy + ch)
      pdf.stroke()

      // LEFT SIDE: BRANDING (Optimized vertical centering)
      try {
          const logoSize = 48; const leftAreaCenter = cx + (splitX - 18 - cx) / 2
          const logoDataURL = await loadImageAsDataURL(contactInfo.logo)
          pdf.addImage(logoDataURL, "PNG", leftAreaCenter - logoSize/2, cy + 18, logoSize, logoSize)
          
          let orgSize = 22; pdf.setFontSize(orgSize); pdf.setFont("helvetica", "bold")
          while (pdf.getTextWidth(contactInfo.organization.toUpperCase()) > (splitX - cx - 20) && orgSize > 10) {
              orgSize -= 1; pdf.setFontSize(orgSize)
          }
          pdf.setTextColor(15, 23, 42)
          pdf.text(contactInfo.organization.toUpperCase(), leftAreaCenter, cy + 82, { align: "center" })
          
          pdf.setFontSize(9); pdf.setFont("helvetica", "normal"); pdf.setTextColor(100, 116, 139)
          pdf.text(contactInfo.tagline || "", leftAreaCenter, cy + 90, { align: "center", maxWidth: splitX - cx - 25 })
      } catch(e) {}

      // RIGHT SIDE: MEMBER INFO
      const rx = splitX + 15
      let nameSize = 26; pdf.setFontSize(nameSize); pdf.setFont("helvetica", "bold")
      const fullName = `${contactInfo.firstName} ${contactInfo.lastName}`.toUpperCase()
      while (pdf.getTextWidth(fullName) > (cx + cw - rx - 15) && nameSize > 14) {
          nameSize -= 0.5; pdf.setFontSize(nameSize)
      }
      pdf.setTextColor(255, 255, 255); pdf.text(fullName, rx, cy + 28)
      
      pdf.setFontSize(14); pdf.setTextColor(245, 158, 11); pdf.setFont("helvetica", "bold")
      pdf.text(contactInfo.title.toUpperCase(), rx, cy + 36)

      // Address (Above icons)
      pdf.setTextColor(148, 163, 184); pdf.setFontSize(9); pdf.setFont("helvetica", "normal")
      const fullAddr = contactInfo.address + ", " + contactInfo.city
      pdf.text(fullAddr.substring(0, 50) + (fullAddr.length > 50 ? "..." : ""), rx, cy + 46)

      // CONTACT GRID (Precision Spacing)
      let ry = cy + 62
      const drawIcon = (x: number, y: number, type: string) => {
          pdf.setDrawColor(15, 23, 42); pdf.setLineWidth(0.4)
          if (type === "phone") {
              // Handset shape
              pdf.roundedRect(x-1.5, y-2, 3, 4, 0.5, 0.5, "S")
              pdf.circle(x, y+1.2, 0.3, "S")
          } else if (type === "email") {
              // Envelope
              pdf.rect(x-2, y-1.5, 4, 3, "S")
              pdf.line(x-2, y-1.5, x, y)
              pdf.line(x+2, y-1.5, x, y)
          } else if (type === "web") {
              // Globe
              pdf.circle(x, y, 2, "S")
              pdf.line(x-2, y, x+2, y)
              pdf.ellipse(x, y, 0.8, 2, "S")
          }
      }

      const addRow = (type: string, val: string) => {
          if (!val) return;
          pdf.setFillColor(245, 158, 11); pdf.circle(rx + 4, ry - 1.5, 4.2, "F")
          drawIcon(rx + 4, ry - 1.5, type)
          
          pdf.setTextColor(244, 244, 245); pdf.setFontSize(11); pdf.setFont("helvetica", "normal")
          pdf.text(val, rx + 12, ry); ry += 11
      }
      addRow("phone", "+91 " + contactInfo.phone)
      addRow("email", contactInfo.email)
      addRow("web", contactInfo.website)

      // QR Code (VCard for direct save)
      const minimalVCard = [
        "BEGIN:VCARD", "VERSION:2.1",
        `N:${contactInfo.lastName};${contactInfo.firstName}`,
        `FN:${contactInfo.firstName} ${contactInfo.lastName}`,
        `ORG:${contactInfo.organization}`,
        `TEL;CELL:+91${contactInfo.phone}`,
        `EMAIL;INTERNET:${contactInfo.email}`,
        "END:VCARD"
      ].join("\r\n");

      const qrSz = 32
      const qrPath = await generateQRCodeDataURL(minimalVCard, { color: { dark: "#FFFFFF", light: "#0f172a" }, errorCorrectionLevel: 'M' })
      pdf.addImage(qrPath, "PNG", cx + cw - qrSz - 5, cy + ch - qrSz - 5, qrSz, qrSz)

      pdf.save(`${contactInfo.firstName}-business-card.pdf`)
    } catch (e) { console.error(e); }
  }

  if (loading || !contactInfo) return null;

  if (showForm) {
    return <LeadForm 
      cardOwner={`${contactInfo.firstName} ${contactInfo.lastName}`} 
      onSubmit={handleLeadSubmit} 
    />;
  }

  const pageUrl = window.location.href;
  const hasSocials = contactInfo.linkedin || contactInfo.instagram || contactInfo.facebook || contactInfo.twitter;

  return (
    <div className="min-h-screen bg-slate-50 p-4 sm:p-6 lg:p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="text-center bg-white rounded-[2rem] shadow-2xl p-8 border border-white/30 relative overflow-hidden">
          <div className="flex flex-col items-center justify-center mb-6">
            <div className="p-1 bg-white rounded-3xl shadow-xl">
              <img src={contactInfo.logo} alt="Logo" className="h-24 w-auto object-contain" crossOrigin="anonymous" />
            </div>
          </div>
          <h1 className="text-4xl font-black text-slate-800 tracking-tighter uppercase">{contactInfo.organization}</h1>
          <p className="text-slate-400 text-sm font-bold tracking-[0.2em] italic mt-2">{contactInfo.tagline}</p>
        </div>

        <div className="bg-white rounded-[2rem] shadow-2xl border border-white/30 overflow-hidden">
          <div className="bg-slate-900 text-white p-6 text-center">
            <h2 className="text-xl font-bold">{contactInfo.organization} Profile</h2>
          </div>

          <div className="p-8 text-center bg-white">
            <div className="flex justify-center mb-10">
                <div className="bg-slate-50 p-5 rounded-3xl shadow-inner border border-slate-100">
                  <QRCodeSVG value={pageUrl} size={220} level="H" includeMargin={true} fgColor="#0f172a" />
                </div>
            </div>

            <div className="mb-10 text-center">
               <h3 className="text-3xl font-black text-slate-800">{contactInfo.firstName} {contactInfo.lastName}</h3>
               <p className="text-blue-600 font-black tracking-widest text-xs uppercase mt-1">{contactInfo.title}</p>
            </div>

            {hasSocials && (
                <div className="flex flex-wrap justify-center gap-4 mb-10">
                    {contactInfo.linkedin && (
                        <a href={contactInfo.linkedin} target="_blank" className="w-12 h-12 border border-slate-200 text-blue-700 rounded-full flex items-center justify-center hover:bg-slate-50 transition-all shadow-sm"><Linkedin /></a>
                    )}
                    {contactInfo.instagram && (
                        <a href={contactInfo.instagram} target="_blank" className="w-12 h-12 border border-slate-200 text-pink-600 rounded-full flex items-center justify-center hover:bg-slate-50 transition-all shadow-sm"><Instagram /></a>
                    )}
                    {contactInfo.facebook && (
                        <a href={contactInfo.facebook} target="_blank" className="w-12 h-12 border border-slate-200 text-blue-600 rounded-full flex items-center justify-center hover:bg-slate-50 transition-all shadow-sm"><Facebook /></a>
                    )}
                    {contactInfo.twitter && (
                        <a href={contactInfo.twitter} target="_blank" className="w-12 h-12 border border-slate-200 text-slate-900 rounded-full flex items-center justify-center hover:bg-slate-50 transition-all shadow-sm"><Twitter /></a>
                    )}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10 text-left">
               <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 flex items-center gap-4 group hover:bg-white hover:shadow-md transition-all">
                  <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center"><Phone className="w-5 h-5"/></div>
                  <div><p className="text-[10px] text-slate-400 font-black uppercase">Call</p><p className="font-bold">+91 {contactInfo.phone}</p></div>
               </div>
               <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 flex items-center gap-4 group hover:bg-white hover:shadow-md transition-all">
                  <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center"><Mail className="w-5 h-5" /></div>
                  <div className="min-w-0"><p className="text-[10px] text-slate-400 font-black uppercase">Email</p><p className="font-bold truncate">{contactInfo.email}</p></div>
               </div>
               <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 flex items-center gap-4 group hover:bg-white hover:shadow-md transition-all">
                  <div className="w-10 h-10 bg-cyan-100 text-cyan-600 rounded-xl flex items-center justify-center"><Globe className="w-5 h-5" /></div>
                  <div className="min-w-0">
                    <p className="text-[10px] text-slate-400 font-black uppercase">Website</p>
                    <a href={contactInfo.website?.startsWith('http') ? contactInfo.website : `https://${contactInfo.website}`} target="_blank" className="font-bold block truncate hover:text-blue-600">{contactInfo.website}</a>
                  </div>
               </div>
               <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 flex items-center gap-4 group hover:bg-white hover:shadow-md transition-all">
                  <div className="w-10 h-10 bg-emerald-100 text-emerald-600 rounded-xl flex items-center justify-center shrink-0"><MapPin className="w-5 h-5" /></div>
                  <div className="min-w-0">
                    <p className="text-[10px] text-slate-400 font-black uppercase">Location</p>
                    <p className="font-bold text-xs truncate">{contactInfo.city}, {contactInfo.state}</p>
                    {contactInfo.mapsLink && (
                       <a href={contactInfo.mapsLink} target="_blank" className="text-[10px] font-black text-blue-600 underline">VIEW ON MAPS</a>
                    )}
                  </div>
               </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <button onClick={downloadVCard} className="flex-1 bg-white border-2 border-slate-200 font-black py-4 px-8 rounded-2xl shadow-xl flex items-center justify-center gap-3 transition-all active:scale-95 hover:bg-slate-50"><Smartphone className="w-5 h-5" /> SAVE CONTACT</button>
              <button onClick={downloadContactPDF} className="flex-1 bg-slate-900 text-white font-black py-4 px-8 rounded-2xl shadow-xl flex items-center justify-center gap-3 transition-all active:scale-95 hover:bg-black search-glass"><Download className="w-5 h-5" /> DOWNLOAD PDF</button>
            </div>
          </div>
        </div>

        <div className="text-center p-10 bg-slate-900 text-white rounded-[2rem] shadow-2xl space-y-2">
           <h4 className="text-3xl font-black">{contactInfo.organization}</h4>
           <p className="text-slate-400 text-xs font-bold uppercase tracking-[0.2em]">{contactInfo.tagline}</p>
        </div>
        <p className="text-center text-[10px] font-extrabold uppercase tracking-[0.4em] text-slate-400 pt-2">
          Powered by{' '}
          <a
            href="https://botivate.in/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-600 hover:text-slate-900 transition-colors"
          >
            Botivate
          </a>
        </p>
      </div>
    </div>
  )
}

export default App

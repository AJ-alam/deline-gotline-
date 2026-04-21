import re

html_code = """
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="max-width:880px;margin:0 auto;background:#fff;border-radius:8px;
              box-shadow:0 4px 24px rgba(0,0,0,0.18);overflow:hidden;border-collapse:collapse;">
  <tr>
    <td colspan="2" style="background:#f0f0f0;border-bottom:1px solid #d0d0d0;padding:8px 12px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td style="font-size:11px;color:#444;font-weight:700;">DGG SECURITY PORTAL v2.0</td>
          <td align="right" style="font-size:10px;color:#666;">SESSION: 04:12m remaining</td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td width="168" valign="top" bgcolor="#1a1a1a" style="border-right:1px solid #333;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr><td style="padding:22px 14px;"><div style="width:24px;height:24px;background:#e5a662;border-radius:4px;"></div></td></tr>
        <tr><td style="padding:0 14px 12px 14px;font-size:9px;color:#555;font-weight:800;letter-spacing:1px;">CORE NAVIGATION</td></tr>
        <tr><td style="padding:6px 14px;font-size:10px;color:#ccc;cursor:pointer;">Dashboard Home</td></tr>
        <tr><td style="background:#222;border-left:2px solid #fff;padding:6px 14px;font-size:10px;color:#fff;font-weight:600;">My Profile</td></tr>
        <tr><td style="padding:6px 14px;font-size:10px;color:#ccc;cursor:pointer;">My Applications</td></tr>
        <tr><td style="padding:6px 14px;font-size:10px;color:#ccc;cursor:pointer;">My Payments</td></tr>
        <tr><td style="padding:6px 14px;font-size:10px;color:#ccc;cursor:pointer;">My Documents</td></tr>
        <tr><td style="padding:24px 14px 12px 14px;font-size:9px;color:#555;font-weight:800;letter-spacing:1px;">ACTIVE FORMS</td></tr>
        <tr><td style="padding:6px 14px;font-size:10px;color:#ccc;cursor:pointer;">Form A - New</td></tr>
        <tr><td style="padding:6px 14px;font-size:10px;color:#ccc;cursor:pointer;">Form C - Cont.</td></tr>
        <tr><td style="padding:40px 14px 20px 14px;"><div style="padding:12px;background:#252525;border-radius:4px;"><div style="font-size:9px;color:#888;">Logged in as:</div><div style="font-size:10px;color:#fff;font-weight:700;margin-top:2px;">Test User</div></div></td></tr>
      </table>
    </td>
    <td valign="top" bgcolor="#fcfcfc">
      <div style="padding:32px;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:32px;">
          <tr>
            <td>
              <h1 style="margin:0;font-size:22px;color:#111;letter-spacing:-0.5px;">Student Registry Record</h1>
              <div style="font-size:11px;color:#666;margin-top:4px;">Electronic Identification & Verification System</div>
            </td>
            <td align="right">
              <span style="background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;padding:4px 10px;border-radius:99px;font-size:10px;font-weight:800;">ACTIVE ELIGIBILITY</span>
            </td>
          </tr>
        </table>

        <div style="padding:24px;background:#fff;border:1px solid #eee;border-radius:6px;margin-bottom:24px;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td width="64" valign="top">
                <div style="width:52px;height:52px;background:#111;color:#fff;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;">TU</div>
              </td>
              <td style="padding-left:20px;">
                <div style="font-size:18px;font-weight:700;color:#111;">Test User (Student)</div>
                <div style="font-size:11px;color:#666;margin-top:2px;">DGG ID: DGG-2025-041 \u00b7 PRIMARY: C-DFN PSSSP</div>
              </td>
              <td align="right">
                <div style="text-align:right;">
                  <div style="font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Profile Completeness</div>
                  <div style="font-size:24px;font-weight:800;color:#111;margin-top:2px;">75%</div>
                </div>
              </td>
            </tr>
          </table>
          <div style="height:6px;background:#f0f0f0;border-radius:3px;margin-top:16px;overflow:hidden;">
            <div style="height:100%;width:75%;background:#111;"></div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">
          <div style="padding:20px;background:#fff;border:1px solid #eee;border-radius:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f5f5f5;padding-bottom:10px;">
              <div style="font-size:11px;font-weight:800;color:#888;text-transform:uppercase;">Personal Information</div>
              <div style="font-size:10px;color:#111;font-weight:700;cursor:pointer;">EDIT</div>
            </div>
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Legal Name</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">Test User</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Date of Birth</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">01 / 01 / 2000</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Email</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">test@deline.ca</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Phone</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">(867) 555-0192</td></tr>
            </table>
          </div>

          <div style="padding:20px;background:#fff;border:1px solid #eee;border-radius:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f5f5f5;padding-bottom:10px;">
              <div style="font-size:11px;font-weight:800;color:#888;text-transform:uppercase;">Eligibility Identifiers</div>
              <div style="font-size:10px;color:#111;font-weight:700;cursor:pointer;">EDIT</div>
            </div>
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Beneficiary #</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">DGG-04812</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Treaty / Status #</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">75201-92102</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Primary Stream</td><td align="right" style="padding:6px 0;font-size:11px;color:#166534;font-weight:700;">C-DFN PSSSP</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Secondary Stream</td><td align="right" style="padding:6px 0;font-size:11px;color:#1e40af;font-weight:700;">DGGR</td></tr>
            </table>
          </div>

          <div style="padding:20px;background:#fff;border:1px solid #eee;border-radius:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f5f5f5;padding-bottom:10px;">
              <div style="font-size:11px;font-weight:800;color:#888;text-transform:uppercase;">Banking & Payouts</div>
              <div style="font-size:10px;color:#111;font-weight:700;cursor:pointer;">EDIT</div>
            </div>
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Bank Institution</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">RBC Royal Bank</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Account Type</td><td align="right" style="padding:6px 0;font-size:11px;color:#111;font-weight:700;">Direct Deposit</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Void Cheque</td><td align="right" style="padding:6px 0;font-size:10px;color:#166534;font-weight:800;">\u2713 VERIFIED</td></tr>
            </table>
          </div>

          <div style="padding:20px;background:#fff;border:1px solid #eee;border-radius:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f5f5f5;padding-bottom:10px;">
              <div style="font-size:11px;font-weight:800;color:#888;text-transform:uppercase;">Verified Documents</div>
              <div style="font-size:10px;color:#111;font-weight:700;cursor:pointer;">VIEW ALL</div>
            </div>
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Transcripts</td><td align="right" style="padding:6px 0;font-size:10px;color:#166534;font-weight:800;">\u2713 VERIFIED</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Proof of Residency</td><td align="right" style="padding:6px 0;font-size:10px;color:#166534;font-weight:800;">\u2713 VERIFIED</td></tr>
              <tr><td style="padding:6px 0;font-size:11px;color:#666;">Letter of Acceptance</td><td align="right" style="padding:6px 0;font-size:10px;color:#cc3333;font-weight:800;">! EXPIRED</td></tr>
            </table>
          </div>
        </div>

        <div style="margin-top:32px;padding:20px;background:#fefce8;border:1px solid #fef08a;border-radius:6px;">
          <div style="font-size:11px;font-weight:800;color:#854d0e;text-transform:uppercase;margin-bottom:8px;">Information Accuracy Declaration</div>
          <div style="font-size:11px;color:#a16207;line-height:1.6;">By accessing this portal, you confirm that all information provided is true and accurate. Any changes to your enrollment, residency, or financial status must be reported to the Deline Got'ine Government within 15 business days.</div>
        </div>
      </div>
    </td>
  </tr>
  <tr>
    <td colspan="2" bgcolor="#111" style="padding:16px 32px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td style="font-size:10px;color:#555;">\u00a9 2025 Deline Got'ine Government \u00b7 Education Division \u00b7 All Rights Reserved</td>
          <td align="right" style="font-size:10px;color:#555;">Privacy Policy \u00b7 Terms of Use \u00b7 System Status</td>
        </tr>
      </table>
    </td>
  </tr>
</table>
"""

def replace_style(match):
    style_str = match.group(1)
    # Convert kebab-case to camelCase
    # But wait, it's easier to just put it in double braces for React
    # Actually, React styles are keys in camelCase
    items = style_str.split(';')
    react_style = []
    for item in items:
        if ':' in item:
            key, val = item.split(':', 1)
            key = key.strip()
            val = val.strip()
            # kebab to camel
            key = re.sub(r'-(.)', lambda m: m.group(1).upper(), key)
            react_style.append(f"{key}: '{val}'")
    return f"style={{{{{', '.join(react_style)}}}}}"

jsx = html_code
jsx = re.sub(r'style="([^"]+)"', replace_style, jsx)
jsx = jsx.replace('colspan', 'colSpan')
jsx = jsx.replace('cellpadding', 'cellPadding')
jsx = jsx.replace('cellspacing', 'cellSpacing')
jsx = jsx.replace('valign', 'vAlign')
jsx = jsx.replace('align', 'textAlign')
jsx = jsx.replace('bgcolor', 'backgroundColor')

# Add className instead of some styles if needed, but let's stick to inline as provided
# Fix textAlign values: textAlign="right" -> style={{textAlign: 'right'}}
jsx = re.sub(r'textAlign="([^"]+)"', r"style={{textAlign: '\1'}}", jsx)

# Handle cases where multiple styles are applied
# (Need to merge style props if they coexist, but here it's simple)

import sys
sys.stdout.reconfigure(encoding='utf-8')
print(jsx)

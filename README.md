# Deline Got’ı̨nę Government (DGG) Student Portal

A modern, high-fidelity administrative and student portal for the Deline Got’ı̨nę Government, built with React, TypeScript, and Vite.

## 📁 Project Structure

The project is organized into a clean, modular architecture:

```text
DGG-src/
├── public/                 # Static assets (backgrounds, legacy icons)
├── src/
│   ├── assets/             # Component-level images and assets
│   ├── components/         # Reusable UI components
│   │   └── Forms/          # Generic form wrappers and logic
│   ├── pages/              # Primary view components
│   │   ├── Forms/          # Specific DGG application forms (A-H)
│   │   ├── Dashboard.tsx   # Student Dashboard
│   │   ├── StaffDashboard.tsx # Unified Staff/Director Management
│   │   └── SignIn/SignUp/  # Authentication views
│   ├── styles/             # Modular CSS for themes and layouts
│   ├── App.tsx             # Main routing logic
│   └── main.tsx            # Application entry point
├── eslint.config.js        # Linting rules
├── index.html              # HTML entry point
├── package.json            # Dependencies and scripts
├── tsconfig.json           # TypeScript configuration
└── vite.config.ts          # Vite build configuration
```

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- npm

### Installation
1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

## 🎨 Design System
The portal uses a strict **Black-and-Gold** aesthetic:
- **Primary Color (Gold)**: `#e5a662`
- **Secondary Color (Dark)**: `#1e293b`
- **Background**: High-fidelity overlays with subtle glassmorphism.

## 🛠️ Key Features
- **Unified SSW & Director Dashboards**: Simplified governance tools for application review and approval.
- **Form Wizardry**: Responsive, multi-step application forms based on DGG policy.
- **Reporting Engine**: Advanced financial and enrollment analytics for governance staff.
- **Authentication**: Secure student and internal staff sign-in flows.

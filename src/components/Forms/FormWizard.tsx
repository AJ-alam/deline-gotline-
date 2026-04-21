import React from 'react';
import '../../styles/forms.css';

interface Step {
  id: number;
  label: string;
}

interface FormWizardProps {
  title: string;
  subtitle: string;
  steps: Step[];
  currentStep: number;
  onStepClick: (stepId: number) => void;
  children: React.ReactNode;
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
  isLastStep?: boolean;
  nextDisabled?: boolean;
  onSubmit?: () => void;
}

const FormWizard: React.FC<FormWizardProps> = ({
  title,
  subtitle,
  steps,
  currentStep,
  onStepClick,
  children,
  onBack,
  onNext,
  nextLabel = "Next Step",
  isLastStep = false,
  nextDisabled = false,
  onSubmit
}) => {
  return (
    <div className="wizard-integrated">
      <div className="wizard-shell-embedded">
        {/* Wizard Header (Sub-header style) */}
        <div className="wizard-header" style={{ borderRadius: '6px 6px 0 0' }}>
          <div className="wizard-header-left">{title}</div>
          <div className="wizard-header-right">
            Step {currentStep} of {steps.length}
          </div>
        </div>

        {/* Step Tabs */}
        <div className="step-tabs">
          {steps.map((step) => (
            <div
              key={step.id}
              className={`step-tab ${currentStep === step.id ? 'active' : ''}`}
              onClick={() => onStepClick(step.id)}
            >
              <div className="step-circle">{step.id}</div> {step.label}
            </div>
          ))}
        </div>

        {/* Wizard Content */}
        <div className="wizard-content">
          <div className="wizard-panel-title">Step {currentStep} — {steps.find(s => s.id === currentStep)?.label}</div>
          <div className="wizard-panel-sub">{subtitle}</div>
          {children}
        </div>

        {/* Wizard Footer */}
        <div className="wizard-footer">
          <button className="wizard-btn-back" onClick={onBack}>
            {currentStep === 1 ? 'Cancel' : '← Back'}
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
            <button 
              className="wizard-btn-next" 
              onClick={isLastStep ? (onSubmit || (() => {})) : onNext}
              disabled={nextDisabled}
              style={nextDisabled ? { background: '#cbd5e1', cursor: 'not-allowed', color: '#64748b', opacity: 0.8 } : {}}
            >
              {isLastStep ? (onSubmit ? 'Submit Application' : nextLabel) : `${nextLabel} →`}
            </button>
            {nextDisabled && !isLastStep && (
              <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600' }}>Please complete all required fields *</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FormWizard;

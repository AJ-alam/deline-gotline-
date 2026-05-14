import React from 'react';

interface FieldHintProps {
  text: string;
}

const FieldHint: React.FC<FieldHintProps> = ({ text }) => (
  <span className="field-hint-wrap" title={text}>
    <span className="field-hint-icon" aria-hidden="true">?</span>
    <span className="field-hint-tooltip" role="tooltip">{text}</span>
  </span>
);

export default FieldHint;

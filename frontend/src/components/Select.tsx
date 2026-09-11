import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';

const ChevronDown = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
);
const ChevronUp = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 15l-6-6-6 6" /></svg>
);
const Check = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
);

export function Select({ value, onValueChange, options, ariaLabel, style }:
  {
    value: string;
    onValueChange: (v: string) => void;
    options: { value: string; label: string }[];
    ariaLabel?: string;
    style?: React.CSSProperties;
  }) {
  const current = options.find(o => o.value === value);
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger className="select-trigger inp" aria-label={ariaLabel} style={style}>
        <span className="select-value">{current ? current.label : value}</span>
        <SelectPrimitive.Icon className="select-icon"><ChevronDown /></SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="select-content" position="popper" sideOffset={4}>
          <SelectPrimitive.ScrollUpButton className="select-scroll">
            <ChevronUp />
          </SelectPrimitive.ScrollUpButton>
          <SelectPrimitive.Viewport className="select-viewport">
            {options.map(o => (
              <SelectPrimitive.Item key={o.value} value={o.value} className="select-item">
                <span className="select-item-indicator"><Check /></span>
                <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
          <SelectPrimitive.ScrollDownButton className="select-scroll">
            <ChevronDown />
          </SelectPrimitive.ScrollDownButton>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

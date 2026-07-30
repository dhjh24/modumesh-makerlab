import type { ReactNode } from 'react';

export interface BadgeProps {
  tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger';
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = 'neutral', children, className = '' }: BadgeProps) {
  return <span className={`mm-badge mm-badge--${tone} ${className}`.trim()}>{children}</span>;
}

/** UI component library placeholder. */

export interface ButtonProps {
  label: string;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
}

export function Button(props: ButtonProps): string {
  return `<button class="mm-button mm-button--${props.variant ?? 'primary'}">${props.label}</button>`;
}

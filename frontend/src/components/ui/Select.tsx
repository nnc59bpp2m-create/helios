import { forwardRef, useId, useState, useEffect, useRef } from 'react'
import { ChevronDown, ChevronUp, Check } from 'lucide-react'
import { clsx } from 'clsx'
import { cn } from '../../lib/utils'

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  helperText?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, helperText, id, ...props }, ref) => {
    const generatedId = useId()
    const selectId = id || generatedId

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={selectId} className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={clsx(
            'w-full appearance-none px-3 py-2 rounded-lg border bg-white dark:bg-surface-800',
            'text-surface-900 dark:text-surface-100 placeholder-surface-400 dark:placeholder-surface-500',
            'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent',
            'disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200',
            error
              ? 'border-red-500 focus:ring-red-500'
              : 'border-surface-300 dark:border-surface-600 hover:border-surface-400 dark:hover:border-surface-500',
            className
          )}
          {...props}
        />
        {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
        {helperText && !error && <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">{helperText}</p>}
      </div>
    )
  }
)

Select.displayName = 'Select'

// Headless UI style Select for more customization
interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface CustomSelectProps {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  className?: string
  triggerClassName?: string
  contentClassName?: string
}

export function CustomSelect({
  value,
  onValueChange,
  options,
  placeholder,
  disabled,
  className,
  triggerClassName,
  contentClassName
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const id = useId()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (triggerRef.current && !triggerRef.current.contains(event.target as Node) &&
          contentRef.current && !contentRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className={clsx('relative inline-block w-full', className)}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={clsx(
          'w-full flex items-center justify-between px-3 py-2 rounded-lg border bg-white dark:bg-surface-800',
          'text-surface-900 dark:text-surface-100',
          'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent',
          'disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200',
          disabled
            ? 'border-surface-300 dark:border-surface-600'
            : 'border-surface-300 dark:border-surface-600 hover:border-surface-400 dark:hover:border-surface-500',
          triggerClassName
        )}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-labelledby={id}
      >
        <span className={clsx('truncate pr-8', value ? '' : 'text-surface-400 dark:text-surface-500')}>
          {value ? options.find(o => o.value === value)?.label : placeholder}
        </span>
        <ChevronDown className={clsx('w-4 h-4 flex-shrink-0 ml-2 text-surface-400', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div
          ref={contentRef}
          className={clsx(
            'absolute z-50 mt-1 w-full max-h-60 overflow-auto rounded-lg border bg-white dark:bg-surface-800',
            'shadow-lg border-surface-200 dark:border-surface-700',
            'animate-in',
            contentClassName
          )}
          role="listbox"
          aria-labelledby={id}
        >
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={value === option.value}
              disabled={option.disabled}
              onClick={() => {
                if (!option.disabled) {
                  onValueChange(option.value)
                  setIsOpen(false)
                }
              }}
              className={clsx(
                'w-full px-3 py-2 text-left text-sm transition-colors',
                value === option.value
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300'
                  : 'text-surface-900 dark:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700',
                option.disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              <span className="flex items-center">
                {value === option.value && <Check className="w-4 h-4 mr-2 flex-shrink-0" />}
                {option.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
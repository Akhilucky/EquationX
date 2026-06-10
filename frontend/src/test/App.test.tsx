import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  it('renders the navigation', () => {
    render(<App />)
    expect(screen.getByText('EquationX')).toBeTruthy()
    expect(screen.getByText('Discover')).toBeTruthy()
    expect(screen.getByText('Equations')).toBeTruthy()
    expect(screen.getByText('Forecast')).toBeTruthy()
    expect(screen.getByText('Explain')).toBeTruthy()
    expect(screen.getByText('Simulate')).toBeTruthy()
  })

  it('renders discover page by default', () => {
    render(<App />)
    expect(screen.getByText('Equation Discovery')).toBeTruthy()
  })
})

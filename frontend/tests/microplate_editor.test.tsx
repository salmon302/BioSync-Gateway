import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { HumanFactorsProvider } from '../src/providers/human-factors-provider'
import MicroplateEditor from '../src/pages/MicroplateEditor'

function renderEditor() {
  return render(
    <MemoryRouter>
      <HumanFactorsProvider>
        <MicroplateEditor />
      </HumanFactorsProvider>
    </MemoryRouter>
  )
}

describe('MicroplateEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the editor title', () => {
    renderEditor()
    expect(screen.getByText('Microplate Editor')).toBeInTheDocument()
  })

  it('defaults to 96-well plate', () => {
    renderEditor()
    expect(screen.getByText('Type: 96-well')).toBeInTheDocument()
    expect(screen.getByText('New 96-well Plate')).toBeInTheDocument()
  })

  it('renders 96 wells in the grid', () => {
    renderEditor()
    const wells = document.querySelectorAll('.well')
    expect(wells.length).toBe(96)
  })

  it('allows switching to 384-well plate', async () => {
    const user = userEvent.setup()
    renderEditor()

    const select = screen.getByRole('combobox')
    await user.selectOptions(select, '384-well')

    expect(screen.getByText('Type: 384-well')).toBeInTheDocument()
    const wells = document.querySelectorAll('.well')
    expect(wells.length).toBe(384)
  })

  it('selects a well on click', async () => {
    const user = userEvent.setup()
    renderEditor()

    // Click A1 by label text
    const a1Well = screen.getByText('A1').closest('.well')!
    await user.click(a1Well)

    await waitFor(() => {
      expect(document.querySelector('.well.selected')).not.toBeNull()
    })

    expect(screen.getByText('Selected: 1 wells')).toBeInTheDocument()
  })

  it('toggles selection on second click', async () => {
    const user = userEvent.setup()
    renderEditor()

    const a1Well = screen.getByText('A1').closest('.well')!
    await user.click(a1Well)

    await waitFor(() => {
      expect(screen.getByText('Selected: 1 wells')).toBeInTheDocument()
    })

    // Re-query after React re-render
    const a1WellAgain = screen.getByText('A1').closest('.well')!
    await user.click(a1WellAgain)

    await waitFor(() => {
      expect(screen.getByText('Selected: 0 wells')).toBeInTheDocument()
    })
    expect(document.querySelector('.well.selected')).toBeNull()
  })

  it('has Import CSV and Export JSON buttons', () => {
    renderEditor()
    expect(screen.getByText('Import CSV')).toBeInTheDocument()
    expect(screen.getByText('Export JSON')).toBeInTheDocument()
  })

  it('has a Clear Selection button that is disabled when no selection', () => {
    renderEditor()
    const clearBtn = screen.getByText('Clear Selection')
    expect(clearBtn).toBeDisabled()
  })

  it('shows keyboard navigation hints', () => {
    renderEditor()
    expect(screen.getByText(/Keyboard Navigation/)).toBeInTheDocument()
    expect(screen.getByText(/arrow keys/)).toBeInTheDocument()
  })

  it('shows selection info section', () => {
    renderEditor()
    expect(screen.getByText('Selection Info')).toBeInTheDocument()
  })

  it('well label shows correct row/col (A1 for first well)', () => {
    renderEditor()
    // A1 = row 0, col 0 → "A1"
    expect(screen.getByText('A1')).toBeInTheDocument()
  })

  it('well label shows correct row/col (H12 for last 96-well)', () => {
    renderEditor()
    // H12 = row 7, col 11
    expect(screen.getByText('H12')).toBeInTheDocument()
  })

  it('drag-select with onMouseEnter covers a range', async () => {
    const user = userEvent.setup()
    renderEditor()

    const wells = document.querySelectorAll('.well')
    // MouseDown on A1 (index 0), mouseEnter on C3 to simulate drag
    await user.pointer({ keys: '[MouseLeft>]', target: wells[0] })
    await user.hover(wells[26]) // C3 = row 2, col 2 → 12*2 + 2 = 26
    await user.pointer({ keys: '[/MouseLeft]' })

    // After drag-end, multiple wells should be selected
    // Selection includes all wells in rect A1..C3 = 3 rows × 3 cols = 9
    const selected = document.querySelectorAll('.well.selected')
    expect(selected.length).toBe(9)
  })
})

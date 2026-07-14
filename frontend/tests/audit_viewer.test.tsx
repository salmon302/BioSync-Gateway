import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import AuditViewer from '../src/pages/AuditViewer'

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch as any

function renderViewer() {
  return render(
    <MemoryRouter>
      <AuditViewer />
    </MemoryRouter>
  )
}

describe('AuditViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default mock: empty entries, ok integrity
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/verify')) {
        return Promise.resolve({
          json: () => Promise.resolve({ integrity: 'ok' }),
        })
      }
      return Promise.resolve({
        json: () =>
          Promise.resolve({
            entries: [],
            total: 0,
          }),
      })
    })
  })

  it('renders the audit viewer title', async () => {
    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('Audit Trail Viewer')).toBeInTheDocument()
    })
  })

  it('renders the Verify Chain button', async () => {
    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('Verify Chain')).toBeInTheDocument()
    })
  })

  it('shows chain integrity OK badge on successful verify', async () => {
    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('✓ Chain Integrity OK')).toBeInTheDocument()
    })
  })

  it('shows chain broken badge when verify returns broken', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/verify')) {
        return Promise.resolve({
          json: () => Promise.resolve({ integrity: 'broken' }),
        })
      }
      return Promise.resolve({
        json: () => Promise.resolve({ entries: [], total: 0 }),
      })
    })

    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('✗ Chain Broken')).toBeInTheDocument()
    })
  })

  it('renders filter dropdown with table options', async () => {
    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('Filter by Table:')).toBeInTheDocument()
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })
  })

  it('renders table headers', async () => {
    renderViewer()
    await waitFor(() => {
      const headers = screen.getAllByRole('columnheader')
      const headerTexts = headers.map(h => h.textContent)
      expect(headerTexts).toContain('ID')
      expect(headerTexts).toContain('Table')
      expect(headerTexts).toContain('Operation')
      expect(headerTexts).toContain('Record ID')
      expect(headerTexts.some(t => t?.includes('Timestamp'))).toBe(true)
      expect(headerTexts).toContain('User')
      expect(headerTexts).toContain('Hash Status')
    })
  })

  it('shows empty state when no entries', async () => {
    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('No audit entries found.')).toBeInTheDocument()
    })
  })

  it('renders audit entries in the table', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/verify')) {
        return Promise.resolve({
          json: () => Promise.resolve({ integrity: 'ok' }),
        })
      }
      return Promise.resolve({
        json: () =>
          Promise.resolve({
            entries: [
              {
                id: 1,
                tableName: 'observations',
                operation: 'INSERT',
                recordId: 100,
                timestamp: '2026-07-13T10:00:00Z',
                userId: 'admin',
                previousHash: 'abc123',
                currentHash: 'def456',
                integrityStatus: 'valid',
              },
              {
                id: 2,
                tableName: 'plates',
                operation: 'UPDATE',
                recordId: 200,
                timestamp: '2026-07-13T10:05:00Z',
                userId: 'user1',
                previousHash: 'def456',
                currentHash: 'ghi789',
                integrityStatus: 'broken',
              },
            ],
            total: 2,
          }),
      })
    })

    renderViewer()

    await waitFor(() => {
      expect(screen.getByText('observations')).toBeInTheDocument()
      expect(screen.getByText('plates')).toBeInTheDocument()
      expect(screen.getByText('✓ Valid')).toBeInTheDocument()
      expect(screen.getByText('✗ Broken')).toBeInTheDocument()
      expect(screen.getByText('Total Entries: 2')).toBeInTheDocument()
    })
  })

  it('pagination buttons render', async () => {
    renderViewer()
    await waitFor(() => {
      expect(screen.getByText('Previous')).toBeInTheDocument()
      expect(screen.getByText('Next')).toBeInTheDocument()
    })
  })

  it('clicking Verify Chain re-verifies', async () => {
    const user = userEvent.setup()
    renderViewer()

    await waitFor(() => {
      expect(screen.getByText('✓ Chain Integrity OK')).toBeInTheDocument()
    })

    // Change mock to return broken on next call
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/verify')) {
        return Promise.resolve({
          json: () => Promise.resolve({ integrity: 'broken' }),
        })
      }
      return Promise.resolve({
        json: () => Promise.resolve({ entries: [], total: 0 }),
      })
    })

    await user.click(screen.getByText('Verify Chain'))

    await waitFor(() => {
      expect(screen.getByText('✗ Chain Broken')).toBeInTheDocument()
    })
  })
})

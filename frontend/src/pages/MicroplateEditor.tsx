import React, { useState, useEffect, useCallback } from 'react'
import { useHumanFactorsContext } from '../providers/human-factors-provider'
import './MicroplateEditor.css'

/**
 * MicroplateEditor Component
 * Implements SRS FR-3.2 - Microplate Editor
 * 
 * Features:
 * - CSS Grid layout (SRS FR-3.2.1)
 * - Well state binding: processed/pending/error/gradient (SRS FR-3.2.2)
 * - Click-to-inspect → FHIR Observation overlay (SRS FR-3.2.3)
 * - Batch selection (drag-select by coordinate range) (SRS FR-3.2.4)
 * - Import/export (CSV, JSON manifests) (SRS FR-3.2.5)
 * - Keyboard navigation (arrow keys) (SRS NFR-U2)
 */
interface WellData {
  row: number
  col: number
  state: 'empty' | 'pending' | 'processed' | 'error'
  sampleId?: string
  concentration?: number
  observation?: any
}

interface PlateData {
  id: number
  name: string
  type: '96-well' | '384-well'
  wells: WellData[]
}

const MicroplateEditor: React.FC = () => {
  const { trackSelectionLatency, trackInteraction } = useHumanFactorsContext()
  const [plateType, setPlateType] = useState<'96-well' | '384-well'>('96-well')
  const [plateData, setPlateData] = useState<PlateData | null>(null)
  const [selectedWells, setSelectedWells] = useState<Set<string>>(new Set())
  const [isDragSelecting, setIsDragSelecting] = useState(false)
  const [selectionStart, setSelectionStart] = useState<{row: number, col: number} | null>(null)
  const [showObservation, setShowObservation] = useState(false)
  const [selectedObservation, setSelectedObservation] = useState<any>(null)
  const [, setImportExportData] = useState<string>('')
  const wellClickStartTime = React.useRef<number>(0)

  // Initialize plate data
  useEffect(() => {
    const rows = plateType === '96-well' ? 8 : 16
    const cols = plateType === '96-well' ? 12 : 24
    
    const wells: WellData[] = []
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        wells.push({
          row,
          col,
          state: 'empty'
        })
      }
    }
    
    setPlateData({
      id: 1,
      name: `New ${plateType} Plate`,
      type: plateType,
      wells
    })
  }, [plateType])

  // Handle well click - SRS FR-3.2.3
  const handleWellClick = useCallback((row: number, col: number) => {
    if (!plateData) return

    const well = plateData.wells.find(w => w.row === row && w.col === col)
    if (!well) return

    // Track selection latency for human factors (FR-3.9.1)
    if (wellClickStartTime.current > 0) {
      trackSelectionLatency(wellClickStartTime.current, 'MicroplateEditor', { row, col, state: well.state })
      wellClickStartTime.current = 0
    }

    if (well.state !== 'empty' && well.observation) {
      setSelectedObservation(well.observation)
      setShowObservation(true)
    }

    // Toggle selection
    const key = `${row}-${col}`
    setSelectedWells(prev => {
      const newSet = new Set(prev)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      return newSet
    })
  }, [plateData, trackSelectionLatency])

  // Handle drag selection - SRS FR-3.2.4
  const handleDragStart = useCallback((row: number, col: number) => {
    setIsDragSelecting(true)
    setSelectionStart({ row, col })
    wellClickStartTime.current = Date.now()
  }, [])

  // Track current mouse position during drag
  const dragEndRef = React.useRef<{ row: number; col: number } | null>(null)

  const handleDragOver = useCallback((row: number, col: number) => {
    if (isDragSelecting) {
      dragEndRef.current = { row, col }
    }
  }, [isDragSelecting])

  const handleDragEnd = useCallback(() => {
    if (!isDragSelecting || !selectionStart || !plateData) return

    const endPos = dragEndRef.current || selectionStart

    // Only process as drag-select if the mouse actually moved to a different well
    if (endPos.row === selectionStart.row && endPos.col === selectionStart.col) {
      // Single click — let handleWellClick handle it
      setIsDragSelecting(false)
      setSelectionStart(null)
      dragEndRef.current = null
      return
    }

    // Select all wells in the rectangle between start and end
    const newSelection = new Set(selectedWells)
    const minRow = Math.min(selectionStart.row, endPos.row)
    const maxRow = Math.max(selectionStart.row, endPos.row)
    const minCol = Math.min(selectionStart.col, endPos.col)
    const maxCol = Math.max(selectionStart.col, endPos.col)

    for (let r = minRow; r <= maxRow; r++) {
      for (let c = minCol; c <= maxCol; c++) {
        newSelection.add(`${r}-${c}`)
      }
    }

    setSelectedWells(newSelection)
    setIsDragSelecting(false)
    setSelectionStart(null)
    dragEndRef.current = null
  }, [isDragSelecting, selectionStart, plateData, selectedWells])

  // Keyboard navigation - SRS NFR-U2
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (selectedWells.size === 0) return
      
      const selectedKeys = Array.from(selectedWells)
      const [lastRow, lastCol] = selectedKeys[selectedKeys.length - 1].split('-').map(Number)
      
      let newRow = lastRow
      let newCol = lastCol
      
      switch (e.key) {
        case 'ArrowUp':
          newRow = Math.max(0, lastRow - 1)
          break
        case 'ArrowDown':
          newRow = Math.min((plateType === '96-well' ? 7 : 15), lastRow + 1)
          break
        case 'ArrowLeft':
          newCol = Math.max(0, lastCol - 1)
          break
        case 'ArrowRight':
          newCol = Math.min((plateType === '96-well' ? 11 : 23), lastCol + 1)
          break
        default:
          return
      }
      
      e.preventDefault()
      handleWellClick(newRow, newCol)
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedWells, plateType, handleWellClick])

  // Import CSV - SRS FR-3.2.5
  const handleImportCSV = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.csv'
    input.onchange = (e: any) => {
      const file = e.target.files[0]
      if (!file) return

      const reader = new FileReader()
      reader.onload = (event) => {
        const text = event.target?.result as string
        const lines = text.trim().split('\n')
        if (lines.length < 2) {
          alert('CSV must have a header row and at least one data row.')
          return
        }

        // Parse header: expected "row,col,state,sampleId,concentration"
        const headers = lines[0].toLowerCase().split(',').map(h => h.trim())

        const updatedWells = new Map<string, Partial<WellData>>()
        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(',').map(c => c.trim())
          if (cols.length < 3) continue

          const row = parseInt(cols[headers.indexOf('row')] ?? '')
          const col = parseInt(cols[headers.indexOf('col')] ?? '')
          if (isNaN(row) || isNaN(col)) continue

          const key = `${row}-${col}`
          updatedWells.set(key, {
            state: (cols[headers.indexOf('state')] as WellData['state']) || 'pending',
            sampleId: cols[headers.indexOf('sampleid')] || undefined,
            concentration: parseFloat(cols[headers.indexOf('concentration')] ?? '') || undefined
          })
        }

        // Apply to plate
        if (plateData) {
          const newWells = plateData.wells.map(w => {
            const update = updatedWells.get(`${w.row}-${w.col}`)
            return update ? { ...w, ...update } : w
          })
          setPlateData({ ...plateData, wells: newWells })
          trackInteraction('csv_import', 'MicroplateEditor', { wellsImported: updatedWells.size })
        }
      }
      reader.readAsText(file)
    }
    input.click()
  }, [plateData, trackInteraction])

  // Export JSON - SRS FR-3.2.5
  const handleExportJSON = useCallback(() => {
    if (!plateData) return
    
    const json = JSON.stringify(plateData, null, 2)
    setImportExportData(json)
    
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `plate-${plateData.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [plateData])

  // Render wells
  const renderWells = () => {
    if (!plateData) return null
    
    return plateData.wells.map(well => {
      const key = `${well.row}-${well.col}`
      const isSelected = selectedWells.has(key)
      
      return (
        <div
          key={key}
          className={`well ${well.state} ${isSelected ? 'selected' : ''}`}
          onClick={() => handleWellClick(well.row, well.col)}
          onMouseDown={() => handleDragStart(well.row, well.col)}
          onMouseEnter={() => handleDragOver(well.row, well.col)}
          onMouseUp={handleDragEnd}
          title={`Well ${String.fromCharCode(65 + well.row)}${well.col + 1}`}
        >
          <span className="well-label">
            {String.fromCharCode(65 + well.row)}{well.col + 1}
          </span>
          {well.sampleId && <span className="well-sample">{well.sampleId}</span>}
        </div>
      )
    })
  }

  return (
    <div className="microplate-editor">
      <div className="microplate-header">
        <h2>Microplate Editor</h2>
        <div className="plate-info">
          <h3>{plateData?.name || 'New Plate'}</h3>
          <p>Type: {plateType}</p>
          <p>Selected: {selectedWells.size} wells</p>
        </div>
      </div>

      <div className="microplate-controls">
        <label>
          Plate Type:
          <select
            value={plateType}
            onChange={(e) => setPlateType(e.target.value as '96-well' | '384-well')}
          >
            <option value="96-well">96-well</option>
            <option value="384-well">384-well</option>
          </select>
        </label>
        <button onClick={handleImportCSV}>Import CSV</button>
        <button onClick={handleExportJSON}>Export JSON</button>
        <button disabled={selectedWells.size === 0}>Clear Selection</button>
      </div>

      <div className={`microplate-grid ${plateType}`}>
        {renderWells()}
      </div>

      <div className="selection-info">
        <h4>Selection Info</h4>
        <p>Selected Wells: {selectedWells.size}</p>
        <p>Drag to select multiple wells (SRS FR-3.2.4)</p>
      </div>

      <div className="keyboard-hints">
        <p><strong>Keyboard Navigation:</strong> Use arrow keys to navigate wells (SRS NFR-U2)</p>
        <p><kbd>↑</kbd> <kbd>↓</kbd> <kbd>←</kbd> <kbd>→</kbd> to move selection</p>
      </div>

      {/* Observation Overlay - SRS FR-3.2.3 */}
      {showObservation && selectedObservation && (
        <div className="observation-overlay">
          <button className="close-btn" onClick={() => setShowObservation(false)}>×</button>
          <h3>FHIR Observation Details</h3>
          <div className="observation-details">
            <p><strong>ID:</strong> {selectedObservation.id}</p>
            <p><strong>Code:</strong> {selectedObservation.code?.coding?.[0]?.display}</p>
            <p><strong>Value:</strong> {selectedObservation.valueQuantity?.value} {selectedObservation.valueQuantity?.unit}</p>
            <p><strong>Timestamp:</strong> {selectedObservation.effectiveDateTime}</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default MicroplateEditor

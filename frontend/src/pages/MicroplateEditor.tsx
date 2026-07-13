import React from 'react'
import './MicroplateEditor.css'

/**
 * MicroplateEditor Component
 * Implements SRS FR-3.2 - Microplate Editor
 * 
 * Stub implementation for Phase 0
 * Full implementation in Phase 3
 */
const MicroplateEditor: React.FC = () => {
  const [plateType, setPlateType] = React.useState<'96-well' | '384-well'>('96-well')

  const renderWells = () => {
    const wells = []
    const rows = plateType === '96-well' ? 8 : 16
    const cols = plateType === '96-well' ? 12 : 24
    
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        wells.push(
          <div
            key={`${row}-${col}`}
            className="well-placeholder"
            title={`Well ${String.fromCharCode(65 + row)}${col + 1}`}
          >
            {String.fromCharCode(65 + row)}{col + 1}
          </div>
        )
      }
    }
    return wells
  }

  return (
    <div className="microplate-editor">
      <h2>Microplate Editor</h2>
      <p className="placeholder-text">
        Phase 0: Stub component - Full implementation in Phase 3
      </p>

      <div className="plate-controls">
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
        <button disabled>Import CSV</button>
        <button disabled>Export JSON</button>
      </div>

      <div className={`plate-grid ${plateType}`}>
        {renderWells()}
      </div>

      <div className="well-details-placeholder">
        <p>Click a well to inspect FHIR Observation details</p>
      </div>
    </div>
  )
}

export default MicroplateEditor

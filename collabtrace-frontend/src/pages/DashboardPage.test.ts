import { describe, expect, it } from 'vitest'
import { rciWeightStorageKey } from './DashboardPage'

describe('RCI personal weight storage', () => {
  it('isolates preferences by both user and repository', () => {
    expect(rciWeightStorageKey(1, 7)).not.toBe(rciWeightStorageKey(2, 7))
    expect(rciWeightStorageKey(1, 7)).not.toBe(rciWeightStorageKey(1, 8))
    expect(rciWeightStorageKey(1, 7)).toBe('collabtrace:rci-weights:user:1:repository:7')
  })
})

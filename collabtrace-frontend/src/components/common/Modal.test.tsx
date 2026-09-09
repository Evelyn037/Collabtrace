import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Modal } from './Modal'

describe('Modal keyboard behavior', () => {
  it('moves focus into the dialog, closes with Escape, and restores prior focus', async () => {
    const close = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(<><button>Trigger</button><Modal open={false} title="Test modal" onClose={close}>Body</Modal></>)
    const trigger = screen.getByRole('button', { name: 'Trigger' })
    trigger.focus()
    rerender(<><button>Trigger</button><Modal open title="Test modal" onClose={close}>Body</Modal></>)
    expect(screen.getByRole('dialog')).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(close).toHaveBeenCalledOnce()
    rerender(<><button>Trigger</button><Modal open={false} title="Test modal" onClose={close}>Body</Modal></>)
    expect(trigger).toHaveFocus()
  })
})

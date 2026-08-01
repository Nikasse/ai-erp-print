import { useEffect, useRef, useState } from 'react'

function App() {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [transactions, setTransactions] = useState([])

  const [amount, setAmount] = useState('')
  const [type, setType] = useState('income')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [formError, setFormError] = useState(null)

  const [filter, setFilter] = useState('all')

  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState(null)

  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatThreadId, setChatThreadId] = useState(null)
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState(null)
  const chatInputRef = useRef(null)

  const fetchSummary = () => {
    fetch('http://localhost:8000/api/summary')
      .then((response) => response.json())
      .then((data) => setSummary(data))
      .catch(() => setError('Не вдалося завантажити дані'))
  }

  const fetchTransactions = () => {
    fetch('http://localhost:8000/api/transactions')
      .then((response) => response.json())
      .then((data) => setTransactions(data))
      .catch(() => setTransactions([]))
  }

  useEffect(() => {
    fetchSummary()
  }, [])

  useEffect(() => {
    fetchTransactions()
  }, [])

  const handleAdd = () => {
    setFormError(null)

    fetch('http://localhost:8000/api/transactions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        amount: Number(amount),
        type,
        category,
        description,
      }),
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Не вдалося додати операцію')
        }
        return data
      })
      .then(() => {
        setAmount('')
        setType('income')
        setCategory('')
        setDescription('')
        fetchTransactions()
        fetchSummary()
      })
      .catch((err) => setFormError(err.message))
  }

  const handleDelete = (id) => {
    if (!window.confirm('Видалити операцію?')) {
      return
    }

    fetch(`http://localhost:8000/api/transactions/${id}`, {
      method: 'DELETE',
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Не вдалося видалити операцію')
        }
        fetchTransactions()
        fetchSummary()
      })
      .catch((err) => alert(err.message))
  }

  const handleAnalyze = () => {
    setAnalyzing(true)
    setAnalysisError(null)
    setAnalysis(null)

    fetch('http://localhost:8000/api/ai/analyze-transactions', {
      method: 'POST',
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Не вдалося виконати аналіз')
        }
        return data
      })
      .then((data) => setAnalysis(data))
      .catch((err) => setAnalysisError(err.message))
      .finally(() => setAnalyzing(false))
  }

  const handleChatSend = () => {
    const trimmed = chatInput.trim()
    if (!trimmed) {
      return
    }

    setChatMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    setChatLoading(true)
    setChatError(null)

    fetch('http://localhost:8000/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: trimmed, thread_id: chatThreadId }),
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Не вдалося отримати відповідь')
        }
        return data
      })
      .then((data) => {
        setChatThreadId(data.thread_id)
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.answer,
            pendingAction: data.pending_action
              ? { ...data.pending_action, cardState: 'pending', resultText: null }
              : null,
          },
        ])
      })
      .catch((err) => setChatError(err.message))
      .finally(() => {
        setChatLoading(false)
        setChatInput('')
        chatInputRef.current?.focus()
      })
  }

  const updatePendingAction = (index, updates) => {
    setChatMessages((prev) =>
      prev.map((msg, i) =>
        i === index && msg.pendingAction
          ? { ...msg, pendingAction: { ...msg.pendingAction, ...updates } }
          : msg
      )
    )
  }

  const handleConfirmAction = (index) => {
    const action = chatMessages[index]?.pendingAction
    if (!action || action.cardState !== 'pending') {
      return
    }

    updatePendingAction(index, { cardState: 'loading' })

    fetch(`http://localhost:8000/api/ai/actions/${action.action_id}/confirm`, {
      method: 'POST',
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Не вдалося підтвердити дію')
        }
        return data
      })
      .then((data) => {
        updatePendingAction(index, {
          cardState: 'confirmed',
          resultText: `Підтверджено. Операція №${data.transaction_id}.`,
        })
        fetchTransactions()
        fetchSummary()
      })
      .catch((err) => {
        updatePendingAction(index, { cardState: 'error', resultText: err.message })
      })
  }

  const handleCancelAction = (index) => {
    const action = chatMessages[index]?.pendingAction
    if (!action || action.cardState !== 'pending') {
      return
    }

    updatePendingAction(index, { cardState: 'loading' })

    fetch(`http://localhost:8000/api/ai/actions/${action.action_id}/cancel`, {
      method: 'POST',
    })
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Не вдалося скасувати дію')
        }
        return data
      })
      .then(() => {
        updatePendingAction(index, { cardState: 'cancelled', resultText: 'Скасовано.' })
      })
      .catch((err) => {
        updatePendingAction(index, { cardState: 'error', resultText: err.message })
      })
  }

  if (error) {
    return <p>{error}</p>
  }

  if (!summary) {
    return <p>Завантаження...</p>
  }

  const filteredTransactions = transactions.filter((tx) => {
    if (filter === 'income') return tx.type === 'income'
    if (filter === 'expense') return tx.type === 'expense'
    return true
  })

  return (
    <div className="page">
      <header className="page-header">
        <h1>Фінансовий облік</h1>
        <p className="page-subtitle">
          Доходи, витрати та AI-аналіз в одному місці
        </p>
      </header>

      <section className="summary-grid">
        <div className="summary-card">
          <span className="summary-label">Доходи</span>
          <span className="summary-value summary-value--income">
            {summary.total_income}
          </span>
        </div>
        <div className="summary-card">
          <span className="summary-label">Витрати</span>
          <span className="summary-value summary-value--expense">
            {summary.total_expense}
          </span>
        </div>
        <div className="summary-card">
          <span className="summary-label">Баланс</span>
          <span
            className={`summary-value ${
              summary.balance >= 0
                ? 'summary-value--income'
                : 'summary-value--expense'
            }`}
          >
            {summary.balance}
          </span>
        </div>
      </section>

      <section className="form-section">
        <h3>Нова операція</h3>
        {formError && <p className="form-error">{formError}</p>}
        <div className="form-row">
          <input
            type="number"
            className="form-input form-input--amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Сума"
          />
          <select
            className="form-input form-input--select"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="income">income</option>
            <option value="expense">expense</option>
          </select>
          <input
            type="text"
            className="form-input form-input--category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Категорія"
          />
          <input
            type="text"
            className="form-input form-input--description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Опис (необов'язково)"
          />
          <button type="button" className="ai-button" onClick={handleAdd}>
            Додати
          </button>
        </div>
      </section>

      <section className="filters-section">
        <div className="filter-switch">
          <button
            type="button"
            className={`filter-btn ${filter === 'all' ? 'filter-btn--active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Усі
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'income' ? 'filter-btn--active' : ''}`}
            onClick={() => setFilter('income')}
          >
            Доходи
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'expense' ? 'filter-btn--active' : ''}`}
            onClick={() => setFilter('expense')}
          >
            Витрати
          </button>
        </div>
      </section>

      <div className="ai-section">
        <h3>AI-аналіз</h3>
        <button
          type="button"
          className="ai-button"
          onClick={handleAnalyze}
          disabled={analyzing}
        >
          {analyzing ? 'Аналізую...' : 'Проаналізувати операції'}
        </button>

        {analysisError && (
          <div className="ai-error-card">
            <strong>Не вдалося виконати аналіз</strong>
            <p style={{ margin: '8px 0 0' }}>{analysisError}</p>
          </div>
        )}

        {analyzing && (
          <div className="ai-cards-grid">
            <div className="ai-skeleton-card" />
            <div className="ai-skeleton-card" />
            <div className="ai-skeleton-card" />
            <div className="ai-skeleton-card" />
          </div>
        )}

        {!analyzing && analysis && (
          <div className="ai-cards-grid">
            <div className="ai-card">
              <h4 className="ai-card-title">Висновок 📊</h4>
              <p>{analysis.summary}</p>
            </div>

            <div className="ai-card">
              <h4 className="ai-card-title">Топ витрат 💸</h4>
              <ul className="ai-list">
                {analysis.top_expense_categories.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="ai-card ai-card--risk">
              <h4 className="ai-card-title">Ризики ⚠️</h4>
              <ul className="ai-list">
                {analysis.risks.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="ai-card ai-card--advice">
              <h4 className="ai-card-title">Поради 💡</h4>
              <ul className="ai-list">
                {analysis.advice.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      <div className="ai-section chat-section">
        <h3>AI-помічник</h3>

        <div className="chat-history">
          {chatMessages.length === 0 && !chatLoading && (
            <p className="chat-empty">
              Постав запитання про свої фінанси, наприклад: "скільки я
              витратив на їжу в червні?"
            </p>
          )}

          {chatMessages.map((msg, index) => (
            <div
              key={index}
              className={`chat-message ${
                msg.role === 'user'
                  ? 'chat-message--user'
                  : 'chat-message--assistant'
              }`}
            >
              <span className="chat-message__author">
                {msg.role === 'user' ? 'Ви' : 'Помічник'}
              </span>
              <p className="chat-message__text">{msg.content}</p>

              {msg.pendingAction && (
                <div className="pending-action-card">
                  <h4 className="pending-action-title">Запропонована дія</h4>

                  <div className="pending-action-rows">
                    {msg.pendingAction.action_type === 'create_transaction' ? (
                      <>
                        <div className="pending-action-row">
                          <span className="pending-action-label">Тип</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.type === 'income' ? 'Дохід' : 'Витрата'}
                          </span>
                        </div>
                        <div className="pending-action-row">
                          <span className="pending-action-label">Сума</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.amount}
                          </span>
                        </div>
                        <div className="pending-action-row">
                          <span className="pending-action-label">Категорія</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.category}
                          </span>
                        </div>
                        <div className="pending-action-row">
                          <span className="pending-action-label">Дата</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.date}
                          </span>
                        </div>
                        <div className="pending-action-row">
                          <span className="pending-action-label">Опис</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.description || 'без опису'}
                          </span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="pending-action-row">
                          <span className="pending-action-label">ID операції</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.transaction_id}
                          </span>
                        </div>
                        <div className="pending-action-row">
                          <span className="pending-action-label">Нова категорія</span>
                          <span className="pending-action-value">
                            {msg.pendingAction.payload.new_category}
                          </span>
                        </div>
                      </>
                    )}
                  </div>

                  {(msg.pendingAction.cardState === 'pending' ||
                    msg.pendingAction.cardState === 'loading') && (
                    <div className="pending-action-buttons">
                      <button
                        type="button"
                        className="ai-button"
                        onClick={() => handleConfirmAction(index)}
                        disabled={msg.pendingAction.cardState === 'loading'}
                      >
                        {msg.pendingAction.cardState === 'loading' ? 'Обробка...' : 'Підтвердити'}
                      </button>
                      <button
                        type="button"
                        className="ai-button ai-button--secondary"
                        onClick={() => handleCancelAction(index)}
                        disabled={msg.pendingAction.cardState === 'loading'}
                      >
                        {msg.pendingAction.cardState === 'loading' ? 'Обробка...' : 'Скасувати'}
                      </button>
                    </div>
                  )}

                  {msg.pendingAction.cardState !== 'pending' &&
                    msg.pendingAction.cardState !== 'loading' && (
                      <p
                        className={`pending-action-result pending-action-result--${msg.pendingAction.cardState}`}
                      >
                        {msg.pendingAction.resultText}
                      </p>
                    )}
                </div>
              )}
            </div>
          ))}

          {chatLoading && (
            <div className="chat-message chat-message--assistant">
              <span className="chat-message__author">Помічник</span>
              <p className="chat-message__text">
                <span className="chat-typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              </p>
            </div>
          )}
        </div>

        {chatError && (
          <div className="ai-error-card">
            <strong>Не вдалося отримати відповідь</strong>
            <p style={{ margin: '8px 0 0' }}>{chatError}</p>
          </div>
        )}

        <div className="chat-input-row">
          <input
            type="text"
            ref={chatInputRef}
            className="form-input chat-input"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !chatLoading) {
                handleChatSend()
              }
            }}
            placeholder="Запитайте про свої фінанси..."
            disabled={chatLoading}
          />
          <button
            type="button"
            className="ai-button"
            onClick={handleChatSend}
            disabled={chatLoading}
          >
            {chatLoading ? 'Друкую...' : 'Надіслати'}
          </button>
        </div>
      </div>

      <section className="table-section">
        {filteredTransactions.length === 0 ? (
          <p className="empty-state">Немає операцій</p>
        ) : (
          <table className="tx-table">
            <thead>
              <tr>
                <th className="tx-table__id">№</th>
                <th>Дата</th>
                <th>Тип</th>
                <th className="tx-table__amount">Сума</th>
                <th>Категорія</th>
                <th>Опис</th>
                <th className="tx-table__actions">Дії</th>
              </tr>
            </thead>
            <tbody>
              {filteredTransactions.map((tx) => (
                <tr key={tx.id}>
                  <td className="tx-table__id">{tx.id}</td>
                  <td>{tx.created_at}</td>
                  <td>
                    <span className={`tx-type tx-type--${tx.type}`}>
                      {tx.type}
                    </span>
                  </td>
                  <td
                    className={`tx-table__amount ${
                      tx.type === 'income'
                        ? 'tx-amount--income'
                        : 'tx-amount--expense'
                    }`}
                  >
                    {tx.amount}
                  </td>
                  <td>{tx.category}</td>
                  <td>{tx.description}</td>
                  <td className="tx-table__actions">
                    <button
                      type="button"
                      className="icon-button"
                      onClick={() => handleDelete(tx.id)}
                      aria-label="Видалити операцію"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

export default App

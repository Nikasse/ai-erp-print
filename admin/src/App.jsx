import { useEffect, useState } from 'react'

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

      <section className="table-section">
        {filteredTransactions.length === 0 ? (
          <p className="empty-state">Немає операцій</p>
        ) : (
          <table className="tx-table">
            <thead>
              <tr>
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

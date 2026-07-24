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
    <div>
      <div>
        <h2>Доходи</h2>
        <p>{summary.total_income}</p>
      </div>
      <div>
        <h2>Витрати</h2>
        <p>{summary.total_expense}</p>
      </div>
      <div>
        <h2>Баланс</h2>
        <p>{summary.balance}</p>
      </div>

      <div>
        <h3>Нова операція</h3>
        {formError && <p>{formError}</p>}
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Сума"
        />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="income">income</option>
          <option value="expense">expense</option>
        </select>
        <input
          type="text"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="Категорія"
        />
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Опис (необов'язково)"
        />
        <button type="button" onClick={handleAdd}>
          Додати
        </button>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setFilter('all')}
          style={{
            fontWeight: filter === 'all' ? 'bold' : 'normal',
            background: filter === 'all' ? '#ddd' : undefined,
          }}
        >
          Усі
        </button>
        <button
          type="button"
          onClick={() => setFilter('income')}
          style={{
            fontWeight: filter === 'income' ? 'bold' : 'normal',
            background: filter === 'income' ? '#ddd' : undefined,
          }}
        >
          Доходи
        </button>
        <button
          type="button"
          onClick={() => setFilter('expense')}
          style={{
            fontWeight: filter === 'expense' ? 'bold' : 'normal',
            background: filter === 'expense' ? '#ddd' : undefined,
          }}
        >
          Витрати
        </button>
      </div>

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

      {filteredTransactions.length === 0 ? (
        <p>Немає операцій</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Дата</th>
              <th>Тип</th>
              <th>Сума</th>
              <th>Категорія</th>
              <th>Опис</th>
              <th>Дії</th>
            </tr>
          </thead>
          <tbody>
            {filteredTransactions.map((tx) => (
              <tr key={tx.id}>
                <td>{tx.created_at}</td>
                <td>{tx.type}</td>
                <td>{tx.amount}</td>
                <td>{tx.category}</td>
                <td>{tx.description}</td>
                <td>
                  <button type="button" onClick={() => handleDelete(tx.id)}>
                    Видалити
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default App

import { Link } from 'react-router'

import { useAuth } from '@auth-kit/react/react'

function Presentation() {
  const { paths, hasFeature } = useAuth()
  return (
    <div className="dari-hero">
      <span className="dari-eyebrow">Département d'informatique · Université de Béjaïa</span>
      <h1 className="dari-hero-title">Les examens du département, de la saisie des notes aux résultats.</h1>
      <p className="dari-hero-text">
        Sessions S1, S2 et rattrapage, sujets confidentiels, notes et coefficients, délibérations, procès-verbaux,
        relevés de notes et réclamations, dans un seul espace sécurisé.
      </p>
      <div className="dari-actions">
        <Link to={paths.login} className="ak-btn ak-btn--primary">Se connecter</Link>
        {hasFeature('register') && <Link to={paths.register} className="ak-btn ak-btn--secondary">Créer un compte</Link>}
      </div>
    </div>
  )
}

export function AccueilPage() {
  const { status, user } = useAuth()
  if (status !== 'authenticated' || !user) return <Presentation />
  return (
    <div className="dari-hero">
      <h1 className="dari-hero-title">Bonjour {user.full_name || user.username}</h1>
      <p className="dari-hero-text">Vous êtes connecté. Les espaces étudiant, enseignant et scolarité arrivent bientôt.</p>
    </div>
  )
}

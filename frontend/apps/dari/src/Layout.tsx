import { Link, NavLink, Outlet } from 'react-router'

import { useAuth } from '@auth-kit/react/react'
import { Avatar, ThemeToggle } from '@auth-kit/react/ui'


function navClass({ isActive }: { isActive: boolean }) {
  return `dari-nav-link${isActive ? ' is-active' : ''}`
}

export function Layout() {
  const { status, user, hasFeature, paths } = useAuth()
  const connecte = status === 'authenticated'

  return (
    <div className="dari-shell">
      <a href="#contenu" className="dari-skip">Aller au contenu</a>
      <header className="dari-header">
        <nav className="dari-nav" aria-label="Navigation principale">
          <Link to="/" className="dari-logo" aria-label="Dari, accueil">
            <span className="dari-logo-mark" aria-hidden="true">D</span>
            <span>Dari</span>
          </Link>

          <div className="dari-nav-end">
            <ThemeToggle />
            {connecte && user ? (
              <NavLink to={paths.profile} className="dari-account" title="Mon profil">
                <Avatar name={user.full_name || user.username} small />
                <span className="dari-account-name">{user.full_name || user.username}</span>
              </NavLink>
            ) : status === 'anonymous' ? (
              <>
                <NavLink to={paths.login} className={navClass}>Connexion</NavLink>
                {hasFeature('register') && (
                  <Link to={paths.register} className="ak-btn ak-btn--primary ak-btn--sm">Créer un compte</Link>
                )}
              </>
            ) : null}
          </div>
        </nav>
      </header>
      <main id="contenu" className="dari-main">
        <Outlet />
      </main>
      <footer className="dari-footer">
        Dari · Gestion des examens du département d'informatique · Université de Béjaïa
      </footer>
    </div>
  )
}

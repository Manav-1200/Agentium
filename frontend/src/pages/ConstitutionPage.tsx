import React, { useEffect, useState } from 'react';
import { Constitution } from '../types';
import { constitutionService } from '../services/constitution';
import { Shield, Book, AlertTriangle, Scale, History } from 'lucide-react';

export const ConstitutionPage: React.FC = () => {
    // ADD THESE MISSING HOOKS:
    const [constitution, setConstitution] = useState<Constitution | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState<{
        preamble: string;
        articles: string;
        prohibited_actions: string;
        sovereign_preferences: string;
    }>({
        preamble: '',
        articles: '',
        prohibited_actions: '',
        sovereign_preferences: ''
    });

    useEffect(() => {
        loadConstitution();
    }, []);

    const loadConstitution = async () => {
        try {
            setIsLoading(true);
            setError(null);
            const data = await constitutionService.getCurrentConstitution();
            setConstitution(data);

            // Initialize form
            setEditForm({
                preamble: data.preamble || '',
                articles: JSON.stringify(data.articles, null, 2),
                prohibited_actions: data.prohibited_actions.join('\n'),
                sovereign_preferences: JSON.stringify(data.sovereign_preferences, null, 2)
            });
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || 'Failed to load constitution');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSave = async () => {
        try {
            // Validate JSON
            const articlesJson = JSON.parse(editForm.articles);
            const prefsJson = JSON.parse(editForm.sovereign_preferences);

            await constitutionService.updateConstitution({
                preamble: editForm.preamble,
                articles: articlesJson,
                prohibited_actions: editForm.prohibited_actions.split('\n').filter(s => s.trim().length > 0),
                sovereign_preferences: prefsJson
            });

            await loadConstitution();
            setIsEditing(false);
        } catch (err: any) {
            console.error(err);
            alert(`Failed to save: ${err.message}`);
        }
    };

    if (isLoading) {
        return <div className="p-6 text-center text-gray-500">Loading constitution...</div>;
    }

    if (error) {
        return (
            <div className="p-6 flex flex-col items-center justify-center h-full text-red-400">
                <AlertTriangle className="w-12 h-12 mb-4" />
                <h2 className="text-xl font-bold">Access Denied / Error</h2>
                <p className="mt-2 text-gray-400">{error}</p>
                <button
                    onClick={loadConstitution}
                    className="mt-4 px-4 py-2 bg-gray-800 rounded hover:bg-gray-700 text-white transition-colors"
                >
                    Retry
                </button>
            </div>
        );
    }

    if (!constitution) return null;

    return (
        <div className="p-6 max-w-4xl mx-auto pb-20">
            <div className="flex items-center justify-between mb-8 border-b border-gray-700 pb-6">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-purple-500/10 rounded-xl">
                        <Book className="w-8 h-8 text-purple-400" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-white">The Constitution of Agentium</h1>
                        <div className="flex items-center gap-3 mt-2 text-sm text-gray-400">
                            <span className="flex items-center gap-1">
                                <History className="w-4 h-4" />
                                Version {constitution.version}
                            </span>
                            <span>•</span>
                            <span>Effective: {new Date(constitution.effective_date).toLocaleDateString()}</span>
                        </div>
                    </div>
                </div>

                <button
                    onClick={() => isEditing ? handleSave() : setIsEditing(true)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${isEditing
                        ? 'bg-green-600 hover:bg-green-500 text-white'
                        : 'bg-gray-800 hover:bg-gray-700 text-gray-200'
                        }`}
                >
                    {isEditing ? 'Save Changes' : 'Edit Constitution'}
                </button>
            </div>

            {isEditing ? (
                <div className="space-y-6">
                    {/* Edit Preamble */}
                    <div className="bg-gray-900/50 p-6 rounded-xl border border-gray-800">
                        <label className="block text-sm font-medium text-gray-400 mb-2">Preamble</label>
                        <textarea
                            className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white h-32"
                            value={editForm.preamble}
                            onChange={e => setEditForm({ ...editForm, preamble: e.target.value })}
                        />
                    </div>

                    {/* Edit Everything Else (JSON/Text) */}
                    <div className="grid grid-cols-1 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Articles (JSON Format)</label>
                            <textarea
                                className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white font-mono text-sm h-64"
                                value={editForm.articles}
                                onChange={e => setEditForm({ ...editForm, articles: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Prohibited Actions (One per line)</label>
                            <textarea
                                className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white h-48"
                                value={editForm.prohibited_actions}
                                onChange={e => setEditForm({ ...editForm, prohibited_actions: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Sovereign Preferences (JSON)</label>
                            <textarea
                                className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white font-mono text-sm h-48"
                                value={editForm.sovereign_preferences}
                                onChange={e => setEditForm({ ...editForm, sovereign_preferences: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="flex justify-end gap-3 mt-6">
                        <button
                            onClick={() => setIsEditing(false)}
                            className="px-4 py-2 text-gray-400 hover:text-white"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold"
                        >
                            Save Amendment
                        </button>
                    </div>
                </div>
            ) : (
                <>
                    {/* View Mode */}
                    <section className="mb-10 text-center">
                        <h2 className="text-xl font-serif italic text-gray-300 mb-4 leading-relaxed max-w-2xl mx-auto">
                            "{constitution.preamble}"
                        </h2>
                        <div className="w-24 h-1 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent mx-auto"></div>
                    </section>

                    {/* Sovereign Preferences */}
                    <section className="mb-8 bg-gray-900/50 p-6 rounded-xl border border-gray-800">
                        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <Shield className="w-5 h-5 text-blue-400" />
                            Sovereign Preferences
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {Object.entries(constitution.sovereign_preferences).map(([key, value]) => (
                                <div key={key} className="bg-gray-800/50 p-3 rounded border border-gray-700/50">
                                    <span className="text-gray-400 text-xs uppercase tracking-wider block mb-1">
                                        {key.replace(/_/g, ' ')}
                                    </span>
                                    <span className="text-gray-200 font-medium">{String(value)}</span>
                                </div>
                            ))}
                        </div>
                    </section>

                    {/* Articles */}
                    <section className="space-y-6">
                        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                            <Scale className="w-6 h-6 text-purple-400" />
                            Articles
                        </h3>

                        {Object.entries(constitution.articles).map(([articleId, content]) => (
                            <div key={articleId} className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-gray-600 transition-colors">
                                <h4 className="text-lg font-bold text-white mb-3 text-purple-200">
                                    {articleId}
                                </h4>
                                <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                                    {content as string}
                                </p>
                            </div>
                        ))}
                    </section>

                    {/* Prohibited Actions */}
                    <section className="mt-10 pt-8 border-t border-gray-800">
                        <h3 className="text-lg font-bold text-red-400 mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5" />
                            Strictly Prohibited Actions
                        </h3>
                        <ul className="space-y-2">
                            {constitution.prohibited_actions.map((action, index) => (
                                <li key={index} className="flex items-start gap-3 bg-red-500/5 p-3 rounded border border-red-500/10 text-red-200/80">
                                    <span className="text-red-500 font-bold">•</span>
                                    {action}
                                </li>
                            ))}
                        </ul>
                    </section>
                </>
            )}
        </div>
    );
};
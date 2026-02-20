import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import type { Skill } from '../../types';
import '../../CSS/SettingsSkills.css';

const SettingsSkills: React.FC = () => {
    const [skills, setSkills] = useState<Skill[]>([]);
    const [loading, setLoading] = useState(true);
    const [editingSkill, setEditingSkill] = useState<Skill | null>(null);
    const [isCreating, setIsCreating] = useState(false);


    // Editor state
    const [editName, setEditName] = useState('');
    const [editDisplayName, setEditDisplayName] = useState('');
    const [editCommand, setEditCommand] = useState('');
    const [editContent, setEditContent] = useState('');
    const [editError, setEditError] = useState('');

    const loadSkills = async () => {
        try {
            setLoading(true);
            const data = await api.skillsApi.getAll();
            setSkills(data);
        } catch (e) {
            console.error("Failed to load skills", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSkills();
    }, []);

    const handleToggle = async (skill: Skill) => {
        try {
            await api.skillsApi.update(skill.skill_name, {
                display_name: skill.display_name,
                slash_command: skill.slash_command,
                content: skill.content,
                enabled: !skill.enabled
            });
            setSkills(skills.map(s => s.id === skill.id ? { ...s, enabled: !s.enabled } : s));
        } catch (e: any) {
            console.error("Failed to toggle skill", e);
            alert(e.message || "Failed to update skill");
        }
    };

    const startEdit = (skill: Skill | null) => {
        if (skill) {
            setEditingSkill(skill);
            setIsCreating(false);
            setEditName(skill.skill_name);
            setEditDisplayName(skill.display_name);
            setEditCommand(skill.slash_command);
            setEditContent(skill.content);
        } else {
            setEditingSkill(null);
            setIsCreating(true);
            setEditName('');
            setEditDisplayName('');
            setEditCommand('');
            setEditContent('');
        }
        setEditError('');
    };

    const handleSave = async () => {
        setEditError('');
        if (!editDisplayName.trim() || !editCommand.trim() || !editContent.trim()) {
            setEditError("All fields are required.");
            return;
        }

        try {
            if (editingSkill) {
                // Update
                await api.skillsApi.update(editingSkill.skill_name, {
                    display_name: editDisplayName,
                    slash_command: editCommand.replace(/^\//, ''), // strip leading slash if user added it
                    content: editContent,
                    enabled: editingSkill.enabled
                });
            } else {
                // Create
                if (!editName.trim()) {
                    setEditError("Internal Name is required for new skills.");
                    return;
                }
                await api.skillsApi.create({
                    skill_name: editName.replace(/[^a-zA-Z0-9_-]/g, '').toLowerCase(),
                    display_name: editDisplayName,
                    slash_command: editCommand.replace(/^\//, ''),
                    content: editContent,
                    enabled: true
                });
            }
            await loadSkills();
            setEditingSkill(null);
            setIsCreating(false);
            setEditName('');
            setEditDisplayName('');
            setEditCommand('');
            setEditContent('');
        } catch (e: any) {
            setEditError(e.message || "Failed to save skill");
        }
    };

    const handleDelete = async (skillName: string) => {
        if (!confirm(`Are you sure you want to delete the ${skillName} skill?`)) return;
        try {
            await api.skillsApi.delete(skillName);
            await loadSkills();
        } catch (e: any) {
            alert(e.message || "Failed to delete skill");
        }
    };

    const handleReset = async (skillName: string) => {
        if (!confirm(`Are you sure you want to reset the ${skillName} skill to defaults? Your changes will be lost.`)) return;
        try {
            await api.skillsApi.reset(skillName);
            await loadSkills();
        } catch (e: any) {
            alert(e.message || "Failed to reset skill");
        }
    };

    if (loading && skills.length === 0) {
        return <div className="settings-skills-loading">Loading skills...</div>;
    }

    return (
        <div className="settings-skills-container">
            <div className="settings-skills-header">
                <div>
                    <h2>Skills</h2>
                    <p>Behavioral rules injected into Clueless's prompt when certain tools are used or slash commands are typed.</p>
                </div>
                {(!isCreating && !editingSkill) && (
                    <button className="create-skill-btn" onClick={() => startEdit(null)}>
                        Add Custom Skill
                    </button>
                )}
            </div>

            {(isCreating || editingSkill) ? (
                <div className="skill-editor">
                    <div className="editor-header">
                        <h3>{editingSkill ? `Edit ${editingSkill.display_name}` : 'Create New Skill'}</h3>
                        <button className="editor-close-btn" onClick={() => { setEditingSkill(null); setIsCreating(false); }}>Cancel</button>
                    </div>

                    {editError && <div className="editor-error">{editError}</div>}

                    <div className="editor-row">
                        <div className="editor-group">
                            <label>Display Name</label>
                            <input
                                type="text"
                                value={editDisplayName}
                                onChange={e => setEditDisplayName(e.target.value)}
                                placeholder="e.g. File System"
                            />
                        </div>
                        <div className="editor-group">
                            <label>Slash Command</label>
                            <div className="input-with-prefix">
                                <span className="prefix">/</span>
                                <input
                                    type="text"
                                    value={editCommand}
                                    onChange={e => setEditCommand(e.target.value.replace(/[^a-zA-Z0-9_-]/g, ''))}
                                    placeholder="e.g. filesystem"
                                />
                            </div>
                        </div>
                    </div>

                    {!editingSkill && (
                        <div className="editor-group">
                            <label>Internal Name (Appears in logs, must be unique, maps to MCP server name for auto-detect)</label>
                            <input
                                type="text"
                                value={editName}
                                onChange={e => setEditName(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                                placeholder="e.g. filesystem"
                            />
                        </div>
                    )}

                    <div className="editor-group">
                        <label>Prompt Content (Markdown supported)</label>
                        <textarea
                            value={editContent}
                            onChange={e => setEditContent(e.target.value)}
                            placeholder="Instructions to inject into the system prompt..."
                            rows={10}
                        />
                    </div>

                    <div className="editor-actions">
                        <button className="save-btn" onClick={handleSave}>Save Skill</button>
                    </div>
                </div>
            ) : (
                <div className="skills-list">
                    {skills.map(skill => (
                        <div key={skill.id} className={`skill-card ${!skill.enabled ? 'disabled' : ''}`}>
                            <div className="skill-card-header">
                                <div className="skill-title-group">
                                    <h3>{skill.display_name}</h3>
                                    <span className="skill-command">/{skill.slash_command}</span>
                                    {skill.is_default && <span className="skill-badge default">Default</span>}
                                    {!skill.is_default && <span className="skill-badge custom">Custom</span>}
                                    {skill.is_modified && <span className="skill-badge modified">Modified</span>}
                                </div>

                                <label className="settings-toggle">
                                    <input
                                        type="checkbox"
                                        checked={skill.enabled}
                                        onChange={() => handleToggle(skill)}
                                    />
                                    <span className="settings-toggle-slider"></span>
                                </label>
                            </div>

                            <div className="skill-card-body">
                                <pre>{skill.content.slice(0, 150)}{skill.content.length > 150 ? '...' : ''}</pre>
                            </div>

                            <div className="skill-card-footer">
                                <div className="skill-footer-left">
                                    <span className="internal-name">Internal: {skill.skill_name}</span>
                                </div>
                                <div className="skill-actions">
                                    <button onClick={() => startEdit(skill)} className="action-btn edit-btn">Edit</button>
                                    {skill.is_default && skill.is_modified && (
                                        <button onClick={() => handleReset(skill.skill_name)} className="action-btn reset-btn">Reset</button>
                                    )}
                                    {!skill.is_default && (
                                        <button onClick={() => handleDelete(skill.skill_name)} className="action-btn delete-btn">Delete</button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default SettingsSkills;

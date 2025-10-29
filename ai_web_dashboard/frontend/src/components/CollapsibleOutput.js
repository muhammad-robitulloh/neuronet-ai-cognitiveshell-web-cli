import React, { useState } from 'react';
import './CollapsibleOutput.css';

const CollapsibleOutput = ({ content }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!content) {
        return null;
    }

    const lines = content.trim().split('\n');
    const isCollapsible = lines.length > 2;

    const toggleExpansion = () => {
        setIsExpanded(!isExpanded);
    };

    const displayedContent = isExpanded ? content : lines.slice(0, 2).join('\n');

    return (
        <div className="collapsible-output">
            <pre className="output-content">{displayedContent}</pre>
            {isCollapsible && (
                <button onClick={toggleExpansion} className="toggle-button">
                    {isExpanded ? 'Show Less' : 'Show More'}
                </button>
            )}
        </div>
    );
};

export default CollapsibleOutput;

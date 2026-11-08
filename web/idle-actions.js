export function createIdleActions(actions,command){
    const choices=['Emote_Greetings','pet','Reaction_Happy_Big','Emote_Wow','Emote_Threaten'].filter(name=>name==='pet'?['Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out'].every(clip=>actions[clip]):actions[name]);
    let elapsed=0;
    return (dt,state)=>{
        if(state==='Sequence_Flying_Idle'||state==='Idle_Happy'){elapsed=0;return;}
        elapsed+=dt;
        if(elapsed>=60&&state==='Idle_Neutral'&&choices.length){elapsed=0;command(choices[Math.floor(Math.random()*choices.length)]);}
    };
}

function openHorseModal(el) {
    const d = el.dataset;
    document.getElementById('mUmaban').innerText = d.umaban + '番';
    document.getElementById('mName').innerText = d.name;
    document.getElementById('mSire').innerText = d.sire || '未登録';
    document.getElementById('mBms').innerText = d.bms || '未登録';
    document.getElementById('mTraits').innerText = d.traits || '該当コースの血統傾向を分析中';
    document.getElementById('mBonus').innerText = d.bonus || '標準適性';
    document.getElementById('mGrade').innerText = d.grade || 'B';
    
    const tip = document.getElementById('mTip');
    if (d.isshinba === 'true') {
        tip.innerHTML = '<span class="text-amber-400 font-bold">【新馬戦モード】</span> 過去走実績がないため、血統（父・母父）の仕上がり早・コース適性スコアを高ウェイトで予想に反映しています。';
    } else {
        tip.innerHTML = '過去走実績・指数・パドック・血統適性を総合加味した指数スコアです。';
    }
    
    document.getElementById('horseDetailModal').classList.remove('hidden');
}

function closeHorseModal() {
    document.getElementById('horseDetailModal').classList.add('hidden');
}
